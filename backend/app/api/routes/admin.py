#from backend.app import db
from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import csv
from io import BytesIO, StringIO
import json
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree.ElementTree import (
    Element,
    SubElement,
    register_namespace,
    tostring,
)
from app.schemas.reference import ReferenceDocumentResponse
from app.schemas.reference import ReviewReferenceRequestPayload
from app.models.reference import ReferenceDocument
from app.api.dependencies import require_roles
from app.core.security import hash_password
from app.db.database import get_db
from app.models.user import User, Role, UserRole
from app.schemas.admin import (
    CreateUserRequest,
    RoleAssignmentRequest,
    UserResponse,
)
from uuid import uuid4
from uuid import UUID
from app.services.audit_service import create_audit_log
from app.models.audit import AuditLog
from app.models.system_setting import SystemSetting
from app.models.model_registry import ModelRegistry
from app.models.reference import (
    ReferenceDocument,
    ReferenceDocumentVersion,
    ReferenceSentence,
)
from app.schemas.reference import DocumentRequest
from app.schemas.reference import ReferenceRequestResponse
from pathlib import Path
from uuid import uuid4
from app.schemas.reference import (
    CreateReferenceAddRequestResponse,
)
from app.services.reference_service import save_reference_file
from fastapi.responses import FileResponse, PlainTextResponse
from app.models.certificate import Certificate
from app.models.plagiarism import (
    PlagiarismAnalysis,
    DocumentRequest as DocumentRequestModel,
)
from app.models.scan import Scan
import hashlib
import hmac
from app.core.config import settings
from app.services.reference_index_service import index_reference_document
from app.schemas.admin import ScanApprovalPayload
from app.schemas.admin import PlagiarismExclusionsPayload
from app.services.plagiarism_exclusion_service import (
    EXCLUDED_PHRASES_KEY,
    EXCLUDED_WORDS_KEY,
    get_plagiarism_exclusions,
)
from app.services.ai_detector_result_service import (
    classifier_model_confidence,
    latest_classifier_results_by_scan,
)
from app.services.document_extraction_service import extract_document
from app.services.plagiarism_model_service import (
    PLAGIARISM_MODEL_SETTING_KEY,
    get_local_embedding_model,
    get_selected_model_name,
    list_local_embedding_models,
)
from app.services.embedding_service import get_embedding_model
from app.services.reference_embedding_service import (
    create_reference_sentence_embeddings,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


class PlagiarismModelPayload(BaseModel):
    model_name: str


def serialize_user(user: User) -> UserResponse:
    roles = [
        user_role.role.role_name
        for user_role in user.user_roles
    ]

    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        status=user.status,
        roles=roles,
    )


@router.get("/plagiarism-exclusions")
def get_admin_plagiarism_exclusions(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    words, phrases = get_plagiarism_exclusions(db)
    return {"words": words, "phrases": phrases}


@router.put("/plagiarism-exclusions")
def update_admin_plagiarism_exclusions(
    payload: PlagiarismExclusionsPayload,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    cleaned: dict[str, list[str]] = {}
    for field_name, terms, allow_phrases in (
        ("words", payload.words, False),
        ("phrases", payload.phrases, True),
    ):
        normalized: list[str] = []
        seen: set[str] = set()
        for value in terms:
            term = value.strip()
            if not term:
                raise HTTPException(
                    status_code=422,
                    detail=f"{field_name.title()} cannot contain blank entries.",
                )
            if len(term) > 120:
                raise HTTPException(
                    status_code=422,
                    detail=f"Each excluded {field_name[:-1]} must be 120 characters or fewer.",
                )
            if not allow_phrases and len(term.split()) != 1:
                raise HTTPException(
                    status_code=422,
                    detail="Excluded words must each contain one word.",
                )
            folded = term.casefold()
            if folded not in seen:
                normalized.append(term)
                seen.add(folded)
        cleaned[field_name] = normalized

    settings_by_key = {
        setting.key: setting
        for setting in db.query(SystemSetting).filter(
            SystemSetting.key.in_(
                [EXCLUDED_WORDS_KEY, EXCLUDED_PHRASES_KEY]
            )
        ).all()
    }
    previous_values = {
        "words": json.loads(settings_by_key[EXCLUDED_WORDS_KEY].value)
        if settings_by_key.get(EXCLUDED_WORDS_KEY)
        and settings_by_key[EXCLUDED_WORDS_KEY].value
        else [],
        "phrases": json.loads(settings_by_key[EXCLUDED_PHRASES_KEY].value)
        if settings_by_key.get(EXCLUDED_PHRASES_KEY)
        and settings_by_key[EXCLUDED_PHRASES_KEY].value
        else [],
    }

    for key, value in (
        (EXCLUDED_WORDS_KEY, cleaned["words"]),
        (EXCLUDED_PHRASES_KEY, cleaned["phrases"]),
    ):
        setting = settings_by_key.get(key)
        if setting is None:
            setting = SystemSetting(key=key)
            db.add(setting)
        setting.value = json.dumps(value, ensure_ascii=False)
        setting.updated_by = current_admin.id
        setting.description = (
            "Words excluded from plagiarism comparison"
            if key == EXCLUDED_WORDS_KEY
            else "Phrases excluded from plagiarism comparison"
        )

    create_audit_log(
        db,
        user_id=current_admin.id,
        action="PLAGIARISM_EXCLUSIONS_UPDATED",
        entity_type="SYSTEM_SETTING",
        old_values=previous_values,
        new_values=cleaned,
    )
    db.commit()
    return cleaned


@router.get("/plagiarism-model")
def get_admin_plagiarism_model(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    return {
        "models": [
            model.as_dict() for model in list_local_embedding_models()
        ],
        "selected_model": get_selected_model_name(db),
    }


@router.put("/plagiarism-model")
def update_admin_plagiarism_model(
    payload: PlagiarismModelPayload,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    local_model = get_local_embedding_model(payload.model_name)
    if local_model is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Choose a compatible local sentence-embedding model "
                "from the models folder."
            ),
        )

    previous_model_name = get_selected_model_name(db)
    if payload.model_name == previous_model_name:
        return {
            "selected_model": previous_model_name,
            "reindexed_sentences": 0,
        }

    try:
        model = get_embedding_model(local_model.path)
        model_dimension = model.get_sentence_embedding_dimension()
        if (
            model_dimension is None
            or model_dimension > settings.embedding_dimension
        ):
            raise ValueError(
                "The selected model's embedding dimension is not supported "
                "by the database vector dimension."
            )

        registered_model = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == local_model.name,
                ModelRegistry.model_type == "EMBEDDING",
            )
            .order_by(ModelRegistry.created_at)
            .first()
        )
        if registered_model is None:
            registered_model = ModelRegistry(
                model_name=local_model.name,
                model_type="EMBEDDING",
                version=local_model.name,
                local_path=str(local_model.path),
                is_active=True,
            )
            db.add(registered_model)
            db.flush()
        else:
            registered_model.local_path = str(local_model.path)

        sentences = (
            db.query(ReferenceSentence)
            .order_by(ReferenceSentence.id)
            .all()
        )
        reindexed_count = 0
        for start in range(0, len(sentences), 128):
            reindexed_count += create_reference_sentence_embeddings(
                db=db,
                sentences=sentences[start : start + 128],
                model_id=registered_model.id,
                batch_size=32,
                model_path=str(local_model.path),
            )

        setting = db.get(SystemSetting, PLAGIARISM_MODEL_SETTING_KEY)
        if setting is None:
            setting = SystemSetting(key=PLAGIARISM_MODEL_SETTING_KEY)
            db.add(setting)
        setting.value = local_model.name
        setting.updated_by = current_admin.id
        setting.description = (
            "Local sentence-embedding model used for plagiarism detection"
        )

        create_audit_log(
            db,
            user_id=current_admin.id,
            action="PLAGIARISM_MODEL_UPDATED",
            entity_type="SYSTEM_SETTING",
            old_values={"model_name": previous_model_name},
            new_values={
                "model_name": local_model.name,
                "reindexed_sentences": reindexed_count,
            },
        )
        db.commit()
        return {
            "selected_model": local_model.name,
            "reindexed_sentences": reindexed_count,
        }
    except (OSError, RuntimeError, ValueError) as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=f"Could not configure the plagiarism model: {error}",
        ) from error


@router.patch("/scans/{scan_id}/approval")
def review_scan_approval(
    scan_id: UUID,
    review: ScanApprovalPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    scan = (
        db.query(Scan)
        .filter(Scan.id == scan_id)
        .first()
    )

    if scan is None:
        raise HTTPException(
            status_code=404,
            detail="Scanned report not found",
        )

    old_status = scan.approval_status

    scan.approval_status = review.decision
    scan.admin_approval_date = datetime.now(timezone.utc)
    scan.reviewed_by = current_user.id
    scan.admin_comments = review.admin_comments

    create_audit_log(
        db,
        user_id=current_user.id,
        action=f"SCAN_{review.decision}",
        entity_type="SCAN",
        entity_id=scan.id,
        old_values={"approval_status": old_status},
        new_values={
            "approval_status": scan.approval_status,
            "admin_comments": scan.admin_comments,
        },
    )

    try:
        db.commit()
        db.refresh(scan)
    except Exception:
        db.rollback()
        raise

    return {
        "id": str(scan.id),
        "approval_status": scan.approval_status,
        "admin_approval_date": (
            scan.admin_approval_date.isoformat()
            if scan.admin_approval_date
            else None
        ),
        "reviewed_by": str(scan.reviewed_by),
        "admin_comments": scan.admin_comments,
    }
# ---------------------------------------------------------
# LIST USERS
# ---------------------------------------------------------

@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    users = (
        db.query(User)
        .filter(User.status != "DELETED")
        .order_by(User.created_at.desc())
        .all()
    )

    return [serialize_user(user) for user in users]


# ---------------------------------------------------------
# CREATE USER
# ---------------------------------------------------------

@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    existing_username = (
        db.query(User)
        .filter(
            User.username == request.username,
            User.status != "DELETED",
        )
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    existing_email = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=409,
            detail="Email already exists",
        )

    role = (
        db.query(Role)
        .filter(Role.role_name == request.role_name.upper())
        .first()
    )

    if not role:
        raise HTTPException(
            status_code=400,
            detail=f"Role '{request.role_name}' does not exist",
        )

    user = User(
        username=request.username,
        email=request.email,
        full_name=request.full_name,
        password_hash=hash_password(request.password),
        status="ACTIVE",
    )

    db.add(user)
    db.flush()

    user_role = UserRole(
        user_id=user.id,
        role_id=role.id,
        assigned_by=current_admin.id,
    )

    db.add(user_role)
    create_audit_log(
    db,
    user_id=current_admin.id,
    action="USER_CREATED",
    entity_type="USER",
    entity_id=user.id,
    old_values=None,
    new_values={
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
        "role": role.role_name,
        },
    )
    db.commit()
    db.refresh(user)

    return serialize_user(user)


# ---------------------------------------------------------
# ACTIVATE USER
# ---------------------------------------------------------

@router.patch(
    "/users/{user_id}/activate",
    response_model=UserResponse,
)
def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.status == "DELETED":
        raise HTTPException(
            status_code=400,
            detail="Deleted users cannot be activated",
        )
    old_values = {
        "status": user.status,
    }
    user.status = "ACTIVE"
    user.deactivated_at = None
    create_audit_log(
    db,
    user_id=current_admin.id,
    action="USER_ACTIVATED",
    entity_type="USER",
    entity_id=user.id,
    old_values=old_values,
    new_values={
        "status": "ACTIVE",
    },
)
    db.commit()
    db.refresh(user)

    return serialize_user(user)


# ---------------------------------------------------------
# DEACTIVATE USER
# ---------------------------------------------------------

@router.patch(
    "/users/{user_id}/deactivate",
    response_model=UserResponse,
)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.status == "DELETED":
        raise HTTPException(
            status_code=400,
            detail="User is already deleted",
        )

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot deactivate your own account",
        )
    old_values = {
        "status": user.status,
    }
    user.status = "INACTIVE"
    create_audit_log(
    db,
    user_id=current_admin.id,
    action="USER_DEACTIVATED",
    entity_type="USER",
    entity_id=user.id,
    old_values=old_values,
    new_values={
        "status": "INACTIVE",
        },
    )
    from datetime import datetime, timezone

    user.deactivated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    return serialize_user(user)


# ---------------------------------------------------------
# SOFT DELETE USER
# ---------------------------------------------------------

@router.delete(
    "/users/{user_id}",
    response_model=UserResponse,
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account",
        )

    if user.status == "DELETED":
        raise HTTPException(
            status_code=400,
            detail="User is already deleted",
        )

    from datetime import datetime, timezone
    old_values = {
        "status": user.status,
    }
    user.status = "DELETED"
    user.deleted_at = datetime.now(timezone.utc)
    create_audit_log(
    db,
    user_id=current_admin.id,
    action="USER_DELETED",
    entity_type="USER",
    entity_id=user.id,
    old_values=old_values,
    new_values={
        "status": "DELETED",
        },
    )
    db.commit()
    db.refresh(user)

    return serialize_user(user)


# ---------------------------------------------------------
# ASSIGN ROLE
# ---------------------------------------------------------

@router.post(
    "/users/{user_id}/roles",
    response_model=UserResponse,
)
def assign_role(
    user_id: str,
    request: RoleAssignmentRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.status == "DELETED":
        raise HTTPException(
            status_code=400,
            detail="Cannot assign role to deleted user",
        )

    role = (
        db.query(Role)
        .filter(Role.role_name == request.role_name.upper())
        .first()
    )

    if not role:
        raise HTTPException(
            status_code=400,
            detail=f"Role '{request.role_name}' does not exist",
        )

    existing_roles = list(user.user_roles)
    previous_role_names = [
        user_role.role.role_name
        for user_role in existing_roles
    ]
    selected_user_role = next(
        (
            user_role
            for user_role in existing_roles
            if user_role.role_id == role.id
        ),
        None,
    )

    for user_role in existing_roles:
        if user_role is not selected_user_role:
            db.delete(user_role)

    if selected_user_role is None:
        db.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
                assigned_by=current_admin.id,
            )
        )
    create_audit_log(
    db,
    user_id=current_admin.id,
    action="ROLE_ASSIGNED",
    entity_type="USER",
    entity_id=user.id,
    old_values={"roles": previous_role_names},
    new_values={
        "roles": [role.role_name],
        "role_id": role.id,
    },
    )
    db.commit()
    db.refresh(user)
    db.expire(user, ["user_roles"])

    return serialize_user(user)


# ---------------------------------------------------------
# REMOVE ROLE
# ---------------------------------------------------------

@router.delete(
    "/users/{user_id}/roles/{role_id}",
    response_model=UserResponse,
)
def remove_role(
    user_id: str,
    role_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user_role = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user.id,
            UserRole.role_id == role_id,
        )
        .first()
    )

    if not user_role:
        raise HTTPException(
            status_code=404,
            detail="Role assignment not found",
        )

    # Prevent an administrator from removing the last ADMIN role
    role = db.query(Role).filter(Role.id == role_id).first()
    create_audit_log(
    db,
    user_id=current_admin.id,
    action="ROLE_REMOVED",
    entity_type="USER",
    entity_id=user.id,
    old_values={
        "role": role.role_name if role else None,
        "role_id": role_id,
    },
    new_values=None,
)
    if role and role.role_name == "ADMIN":
        admin_count = (
            db.query(UserRole)
            .join(Role)
            .filter(Role.role_name == "ADMIN")
            .count()
        )

        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last ADMIN role",
            )

    db.delete(user_role)
    db.commit()
    db.refresh(user)

    return serialize_user(user)



@router.get(
    "/requests",
    response_model=list[ReferenceRequestResponse],
)
def get_reference_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    requests = (
        db.query(DocumentRequest)
        .order_by(DocumentRequest.created_at.desc())
        .all()
    )

    return [
        ReferenceRequestResponse(
            id=str(item.id),
            request_type=item.request_type,
            requested_by=str(item.requested_by),
            reference_document_id=(
                str(item.reference_document_id)
                if item.reference_document_id
                else None
            ),
            title=item.title,
            reason=item.reason,
            status=item.status,
            reviewed_by=(
                str(item.reviewed_by)
                if item.reviewed_by
                else None
            ),
            reviewed_at=(
                item.reviewed_at.isoformat()
                if item.reviewed_at
                else None
            ),
            rejection_reason=item.rejection_reason,
            admin_comments=item.admin_comments,
            created_at=item.created_at.isoformat(),
            pending_file_name=_request_file_name(item.admin_comments),
        )
        for item in requests
    ]

@router.patch(
    "/requests/{request_id}/review",
    response_model=ReferenceRequestResponse,
)
def review_reference_request(
    request_id: UUID,
    review: ReviewReferenceRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    document_request = (
        db.query(DocumentRequest)
        .filter(DocumentRequest.id == request_id)
        .first()
    )

    if not document_request:
        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    if document_request.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail="Only pending requests can be reviewed",
        )

    if (
        review.decision == "REJECTED"
        and not review.rejection_reason
    ):
        raise HTTPException(
            status_code=400,
            detail="Rejection reason is required",
        )
    reference_to_index = None
    # --------------------------------------------------
    # APPROVAL
    # --------------------------------------------------

    if review.decision == "APPROVED":

        if document_request.request_type == "DELETE":

            reference = (
                db.query(ReferenceDocument)
                .filter(
                    ReferenceDocument.id
                    == document_request.reference_document_id
                )
                .first()
            )

            if not reference:
                raise HTTPException(
                    status_code=404,
                    detail="Reference document not found",
                )

            reference.status = "DELETED"

            create_audit_log(
                db,
                user_id=current_user.id,
                action="REFERENCE_DELETED",
                entity_type="REFERENCE_DOCUMENT",
                entity_id=reference.id,
                old_values={
                    "status": reference.status
                },
                new_values={
                    "status": "DELETED"
                },
            )

        elif document_request.request_type == "UPDATE":

            reference = (
                db.query(ReferenceDocument)
                .filter(
                    ReferenceDocument.id
                    == document_request.reference_document_id
                )
                .first()
            )

            if not reference:
                raise HTTPException(
                    status_code=404,
                    detail="Reference document not found",
                )

            old_title = reference.title

            reference.title = document_request.title

            create_audit_log(
                db,
                user_id=current_user.id,
                action="REFERENCE_UPDATED",
                entity_type="REFERENCE_DOCUMENT",
                entity_id=reference.id,
                old_values={
                    "title": old_title
                },
                new_values={
                    "title": reference.title
                },
            )

        elif document_request.request_type == "ADD":
            if not document_request.admin_comments:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded document information is missing",
                )

            metadata = {}

            for line in document_request.admin_comments.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    metadata[key] = value

            file_path = metadata.get("FILE_PATH")
            file_name = metadata.get("FILE_NAME")
            file_size = metadata.get("FILE_SIZE")
            mime_type = metadata.get("MIME_TYPE")
            sha256_hash = metadata.get("SHA256")

            if not all([
                file_path,
                file_name,
                file_size,
                mime_type,
                sha256_hash,
            ]):
                raise HTTPException(
                    status_code=400,
                    detail="Incomplete uploaded document information",
                )
            
            source_path = Path(file_path)
            #source_path.replace(permanent_path)
            if not source_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail="Uploaded document file not found",
                )

    # -----------------------------------------------
    # Final duplicate check
    # -----------------------------------------------

            existing_reference = (
                db.query(ReferenceDocument)
                .filter(
                    ReferenceDocument.sha256_hash
                    == sha256_hash,
                    ReferenceDocument.status != "DELETED",
                )
                .first()
            )

            if existing_reference:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This document already exists in "
                        "the reference database."
                    ),
                )

    # -----------------------------------------------
    # Move document into permanent reference storage
    # -----------------------------------------------

            extension = source_path.suffix.lower()

            permanent_filename = (
                f"{uuid4()}{extension}"
            )

            permanent_path = (
                Path(settings.upload_dir)
                / "reference_documents"
                / permanent_filename
            )

            permanent_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            source_path.replace(permanent_path)

    # -----------------------------------------------
    # Create reference document
    # -----------------------------------------------

            reference = ReferenceDocument(
                title=document_request.title,
                document_type="FTER",
                file_name=file_name,
                file_path=str(permanent_path),
                file_size=int(file_size),
                mime_type=mime_type,
                sha256_hash=sha256_hash,
                status="ACTIVE",
                current_version=1,
                added_by=document_request.requested_by,
                approved_by=current_user.id,
                approved_at=datetime.now(timezone.utc),
            )

            db.add(reference)
            db.flush()

            # Create the initial version required by the indexing service.
            version = ReferenceDocumentVersion(
                reference_document_id=reference.id,
                version_number=1,
                file_name=file_name,
                file_path=str(permanent_path),
                sha256_hash=sha256_hash,
                uploaded_by=document_request.requested_by,
                approved_by=current_user.id,
                approved_at=datetime.now(timezone.utc),
                change_reason="Approved instructor reference upload",
            )

            db.add(version)
            db.flush()

            document_request.reference_document_id = reference.id
            reference_to_index = reference

            create_audit_log(
                db,
                user_id=current_user.id,
                action="REFERENCE_CREATED_FROM_REQUEST",
                entity_type="REFERENCE_DOCUMENT",
                entity_id=reference.id,
                new_values={
                    "title": reference.title,
                    "sha256_hash": reference.sha256_hash,
                    "source_request_id": str(document_request.id),
                    "version": 1,
                },
            )
    # --------------------------------------------------
    # UPDATE REQUEST STATUS
    # --------------------------------------------------

    document_request.status = review.decision
    document_request.reviewed_by = current_user.id
    document_request.reviewed_at = datetime.now(timezone.utc)
    document_request.admin_comments = review.admin_comments

    if review.decision == "REJECTED":
        document_request.rejection_reason = (
            review.rejection_reason
        )

    create_audit_log(
        db,
        user_id=current_user.id,
        action=f"REFERENCE_REQUEST_{review.decision}",
        entity_type="DOCUMENT_REQUEST",
        entity_id=document_request.id,
        new_values={
            "status": review.decision,
            "admin_comments": review.admin_comments,
            "rejection_reason": review.rejection_reason,
        },
    )




    db.commit()
    db.refresh(document_request)

    # Index only newly approved Instructor ADD references.
    if reference_to_index is not None:
        reference_id = str(reference_to_index.id)

        try:
            sentence_count = index_reference_document(
                db=db,
                reference_document=reference_to_index,
            )

            create_audit_log(
                db,
                user_id=current_user.id,
                action="REFERENCE_INDEXED",
                entity_type="REFERENCE_DOCUMENT",
                entity_id=reference_to_index.id,
                new_values={
                    "version": reference_to_index.current_version,
                    "sentence_count": sentence_count,
                    "trigger": "INSTRUCTOR_REQUEST_APPROVAL",
                },
            )
            db.commit()

            print(
                f"Reference indexed successfully: "
                f"{reference_id}, sentences={sentence_count}"
            )

        except Exception as exc:
            db.rollback()
            print(
                f"Reference indexing failed for "
                f"{reference_id}: {exc}"
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "The reference approval was saved, but "
                    f"indexing failed for reference {reference_id}. "
                    "Check backend logs and retry indexing."
                ),
            )


    return ReferenceRequestResponse(
        id=str(document_request.id),
        request_type=document_request.request_type,
        requested_by=str(document_request.requested_by),
        reference_document_id=(
            str(document_request.reference_document_id)
            if document_request.reference_document_id
            else None
        ),
        title=document_request.title,
        reason=document_request.reason,
        status=document_request.status,
        reviewed_by=(
            str(document_request.reviewed_by)
            if document_request.reviewed_by
            else None
        ),
        reviewed_at=(
            document_request.reviewed_at.isoformat()
            if document_request.reviewed_at
            else None
        ),
        rejection_reason=document_request.rejection_reason,
        admin_comments=document_request.admin_comments,
        created_at=document_request.created_at.isoformat(),
        pending_file_name=_request_file_name(
            document_request.admin_comments
        ),
    )


def _request_file_metadata(admin_comments: str | None) -> dict[str, str]:
    if not admin_comments:
        return {}
    metadata: dict[str, str] = {}
    for line in admin_comments.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"FILE_PATH", "FILE_NAME"} and value:
            metadata[key] = value
    return metadata


def _request_file_name(admin_comments: str | None) -> str | None:
    return _request_file_metadata(admin_comments).get("FILE_NAME")


@router.get(
    "/requests/{request_id}/file"
)
def get_reference_request_file(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    request = (
        db.query(DocumentRequest)
        .filter(
            DocumentRequest.id == request_id
        )
        .first()
    )

    if not request:
        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    if request.request_type != "ADD":
        raise HTTPException(
            status_code=400,
            detail="This request does not contain an uploaded ADD document",
        )

    metadata = _request_file_metadata(request.admin_comments)
    file_path = metadata.get("FILE_PATH")
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail="Pending file path not found",
        )

    path = Path(file_path)

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Pending document file not found",
        )

    filename = metadata.get("FILE_NAME", path.name)
    extension = Path(filename).suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type=media_types.get(extension, "application/octet-stream"),
        content_disposition_type=(
            "inline" if extension in {".pdf", ".txt"} else "attachment"
        ),
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/requests/{request_id}/preview",
    response_class=PlainTextResponse,
)
def preview_reference_request_file(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    request = (
        db.query(DocumentRequest)
        .filter(DocumentRequest.id == request_id)
        .first()
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.request_type != "ADD":
        raise HTTPException(
            status_code=400,
            detail="This request does not contain an uploaded ADD document",
        )

    metadata = _request_file_metadata(request.admin_comments)
    file_path = metadata.get("FILE_PATH")
    filename = metadata.get("FILE_NAME")
    if not file_path or not filename:
        raise HTTPException(
            status_code=404,
            detail="Pending file information not found",
        )

    path = Path(file_path)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Pending document file not found",
        )
    if Path(filename).suffix.lower() != ".docx":
        raise HTTPException(
            status_code=415,
            detail="Text extraction preview is only available for DOCX files.",
        )

    pages = extract_document(path)
    text = "\n\n".join(page.raw_text for page in pages)
    return PlainTextResponse(
        text,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


# ============================================================
# ADMIN CERTIFICATE MANAGEMENT
# ============================================================


def build_admin_certificate_response(
    db: Session,
    certificate: Certificate,
):
    """
    Build certificate details for the Admin dashboard.
    """

    # --------------------------------------------------------
    # Find associated scan
    # --------------------------------------------------------

    scan = (
        db.query(Scan)
        .filter(
            Scan.id == certificate.scan_id
        )
        .first()
    )

    if not scan:
        return {
            "id": str(certificate.id),
            "scan_id": str(certificate.scan_id),
            "certificate_number": certificate.certificate_number,
            "document_title": None,
            "generated_at": (
                certificate.generated_at.isoformat()
                if certificate.generated_at
                else None
            ),
            "generated_by": str(certificate.generated_by),
            "certificate_hash": certificate.certificate_hash,
            "status": certificate.status,
            "plagiarism_score_percent": None,
            "ai_score": None,
            "ai_confidence": None,
            "ai_status": "NOT_AVAILABLE",
            "user": None,
        }

    # --------------------------------------------------------
    # Find latest plagiarism analysis
    # --------------------------------------------------------

    analysis = (
        db.query(PlagiarismAnalysis)
        .filter(
            PlagiarismAnalysis.scan_id == scan.id
        )
        .order_by(
            PlagiarismAnalysis.created_at.desc()
        )
        .first()
    )

    plagiarism_score = None

    if (
        analysis
        and analysis.overall_similarity is not None
    ):
        plagiarism_score = round(
            float(analysis.overall_similarity) * 100,
            2,
        )

    classifier = latest_classifier_results_by_scan(db, [scan.id]).get(scan.id)

    # --------------------------------------------------------
    # Identify the document owner
    # --------------------------------------------------------

    user_id = scan.owner_id or scan.scanned_by

    document_user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
        if user_id
        else None
    )

    # --------------------------------------------------------
    # Identify the administrator who generated it
    # --------------------------------------------------------

    generated_by_user = (
        db.query(User)
        .filter(
            User.id == certificate.generated_by
        )
        .first()
    )

    return {
        "id": str(certificate.id),
        "scan_id": str(certificate.scan_id),
        "certificate_number": certificate.certificate_number,
        "document_title": scan.title,
        "generated_at": (
            certificate.generated_at.isoformat()
            if certificate.generated_at
            else None
        ),
        "generated_by": str(certificate.generated_by),
        "generated_by_name": (
            generated_by_user.full_name
            if generated_by_user
            else None
        ),
        "certificate_hash": certificate.certificate_hash,
        "status": certificate.status,
        "plagiarism_score_percent": plagiarism_score,
        "ai_score": (
            float(classifier.score)
            if classifier is not None
            and classifier.status == "COMPLETED"
            and classifier.score is not None
            else None
        ),
        "ai_confidence": (
            classifier_model_confidence(classifier)
            if classifier is not None and classifier.status == "COMPLETED"
            else None
        ),
        "ai_status": (
            classifier.status if classifier is not None else "NOT_AVAILABLE"
        ),
        "user": (
            {
                "id": str(document_user.id),
                "username": document_user.username,
                "full_name": document_user.full_name,
                "email": document_user.email,
            }
            if document_user
            else None
        ),
    }


# ============================================================
# LIST ALL CERTIFICATES
# GET /admin/certificates
# ============================================================

@router.get("/certificates")
def list_admin_certificates(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    certificates = (
        db.query(Certificate)
        .order_by(
            Certificate.generated_at.desc()
        )
        .all()
    )

    return [
        build_admin_certificate_response(
            db,
            certificate,
        )
        for certificate in certificates
    ]


# ============================================================
# GET CERTIFICATE DETAILS
# GET /admin/certificates/{certificate_id}
# ============================================================

@router.get("/certificates/{certificate_id}")
def get_admin_certificate(
    certificate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    certificate = (
        db.query(Certificate)
        .filter(
            Certificate.id == certificate_id
        )
        .first()
    )

    if not certificate:
        raise HTTPException(
            status_code=404,
            detail="Certificate not found.",
        )

    return build_admin_certificate_response(
        db,
        certificate,
    )


# ============================================================
# DOWNLOAD CERTIFICATE PDF
# GET /admin/certificates/{certificate_id}/download
# ============================================================

@router.get(
    "/certificates/{certificate_id}/download"
)
def download_admin_certificate(
    certificate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    certificate = (
        db.query(Certificate)
        .filter(
            Certificate.id == certificate_id
        )
        .first()
    )

    if not certificate:
        raise HTTPException(
            status_code=404,
            detail="Certificate not found.",
        )

    certificate_path = Path(
        certificate.certificate_path
    )

    if not certificate_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Certificate PDF file was not found."
            ),
        )
    create_audit_log(
    db,
    user_id=current_user.id,
    action="CERTIFICATE_DOWNLOAD_REQUESTED",
    entity_type="CERTIFICATE",
    entity_id=certificate.id,
    new_values={
        "certificate_number": certificate.certificate_number,
        "outcome": "FILE_AVAILABLE",
    },
    )

    db.commit()
    return FileResponse(
        path=str(certificate_path),
        filename=(
            f"{certificate.certificate_number}.pdf"
        ),
        media_type="application/pdf",
    )

# ============================================================
# VERIFY CERTIFICATE INTEGRITY
# GET /admin/certificates/verify/{certificate_number}
# ============================================================

@router.get(
    "/certificates/verify/{certificate_number}"
)
def verify_admin_certificate(
    certificate_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    # --------------------------------------------------------
    # Find certificate using its certificate number
    # --------------------------------------------------------

    certificate = (
        db.query(Certificate)
        .filter(
            Certificate.certificate_number
            == certificate_number
        )
        .first()
    )

    if not certificate:
        raise HTTPException(
            status_code=404,
            detail="Certificate not found.",
        )

    # --------------------------------------------------------
    # Ensure a hash was recorded during generation
    # --------------------------------------------------------

    if not certificate.certificate_hash:
        return {
            "certificate_number": (
                certificate.certificate_number
            ),
            "verification_status": "UNVERIFIABLE",
            "integrity_valid": None,
            "message": (
                "No recorded SHA-256 hash is available "
                "for this certificate."
            ),
        }

    # --------------------------------------------------------
    # Check whether the stored PDF exists
    # --------------------------------------------------------

    certificate_path = Path(
        certificate.certificate_path
    )

    if not certificate_path.is_file():
        return {
            "certificate_number": (
                certificate.certificate_number
            ),
            "verification_status": "FILE_MISSING",
            "integrity_valid": False,
            "message": (
                "The certificate PDF could not be found."
            ),
        }

    # --------------------------------------------------------
    # Calculate SHA-256 from the current PDF
    # Read in chunks to avoid loading the whole file
    # into memory.
    # --------------------------------------------------------

    sha256 = hashlib.sha256()

    try:
        with certificate_path.open("rb") as pdf_file:
            for chunk in iter(
                lambda: pdf_file.read(1024 * 1024),
                b"",
            ):
                sha256.update(chunk)

        calculated_hash = sha256.hexdigest()

    except OSError:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to read the certificate PDF "
                "for verification."
            ),
        )

    # --------------------------------------------------------
    # Compare calculated and recorded hashes
    # --------------------------------------------------------

    integrity_valid = hmac.compare_digest(
        calculated_hash.lower(),
        certificate.certificate_hash.lower(),
    )

    if integrity_valid:
        verification_status = "VERIFIED"
        message = (
        "The certificate PDF matches its recorded "
        "SHA-256 hash."
    )
        audit_action = "CERTIFICATE_VERIFIED"
    else:
        verification_status = "HASH_MISMATCH"
        message = (
            "The certificate PDF does not match its "
            "recorded SHA-256 hash."
        )
        audit_action = "CERTIFICATE_VERIFICATION_FAILED"

    create_audit_log(
        db,
        user_id=current_user.id,
        action=audit_action,
        entity_type="CERTIFICATE",
        entity_id=certificate.id,
        new_values={
            "certificate_number": certificate.certificate_number,
            "outcome": verification_status,
        },
    )

    db.commit()
    # --------------------------------------------------------
    # Return only verification information
    # Do not expose the file path or user details.
    # --------------------------------------------------------

    return {
        "certificate_number": (
            certificate.certificate_number
        ),
        "verification_status": verification_status,
        "integrity_valid": integrity_valid,
        "message": message,
    }



# ============================================================
# ADMIN AUDIT LOG VIEWER
# ============================================================

from fastapi import Query


# ============================================================
# LIST AUDIT LOGS
# GET /admin/audit-logs
# ============================================================

def _filtered_audit_log_query(
    db: Session,
    action: str | None,
    entity_type: str | None,
    user_id: UUID | None,
    start_date: datetime | None,
    end_date: datetime | None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must not be after end_date.",
        )

    query = db.query(AuditLog)
    if action:
        query = query.filter(
            func.lower(AuditLog.action).contains(
                action.strip().lower(),
                autoescape=True,
            )
        )
    if entity_type:
        query = query.filter(
            func.lower(AuditLog.entity_type).contains(
                entity_type.strip().lower(),
                autoescape=True,
            )
        )
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    return query


def _audit_log_export_rows(db: Session, logs: list[AuditLog]) -> list[list[str]]:
    user_ids = {log.user_id for log in logs if log.user_id is not None}
    users_by_id = {}
    if user_ids:
        users_by_id = {
            user.id: user.full_name
            for user in db.query(User).filter(User.id.in_(user_ids)).all()
        }

    def value(item) -> str:
        if item is None:
            return ""
        if isinstance(item, (dict, list)):
            return json.dumps(item, ensure_ascii=False, sort_keys=True)
        return str(item)

    return [
        [
            str(log.id),
            log.created_at.isoformat() if log.created_at else "",
            log.action,
            value(log.entity_type),
            value(log.entity_id),
            users_by_id.get(log.user_id, "") if log.user_id else "",
            value(log.ip_address),
            value(log.old_values),
            value(log.new_values),
        ]
        for log in logs
    ]


def _xlsx_column_name(number: int) -> str:
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _build_audit_log_xlsx(headers: list[str], rows: list[list[str]]) -> bytes:
    spreadsheet_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    office_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    content_types_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    register_namespace("x", spreadsheet_ns)
    register_namespace("r", office_rel_ns)
    register_namespace("pr", package_rel_ns)
    register_namespace("ct", content_types_ns)

    worksheet = Element(f"{{{spreadsheet_ns}}}worksheet")
    sheet_data = SubElement(worksheet, f"{{{spreadsheet_ns}}}sheetData")
    for row_number, values in enumerate([headers, *rows], start=1):
        row_element = SubElement(
            sheet_data,
            f"{{{spreadsheet_ns}}}row",
            {"r": str(row_number)},
        )
        for column_number, value in enumerate(values, start=1):
            cell = SubElement(
                row_element,
                f"{{{spreadsheet_ns}}}c",
                {
                    "r": f"{_xlsx_column_name(column_number)}{row_number}",
                    "t": "inlineStr",
                },
            )
            inline_string = SubElement(cell, f"{{{spreadsheet_ns}}}is")
            text = SubElement(inline_string, f"{{{spreadsheet_ns}}}t")
            text.text = value

    workbook = Element(f"{{{spreadsheet_ns}}}workbook")
    sheets = SubElement(workbook, f"{{{spreadsheet_ns}}}sheets")
    SubElement(
        sheets,
        f"{{{spreadsheet_ns}}}sheet",
        {"name": "Audit Logs", "sheetId": "1", f"{{{office_rel_ns}}}id": "rId1"},
    )

    root_relationships = Element(f"{{{package_rel_ns}}}Relationships")
    SubElement(
        root_relationships,
        f"{{{package_rel_ns}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{office_rel_ns}/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    workbook_relationships = Element(f"{{{package_rel_ns}}}Relationships")
    SubElement(
        workbook_relationships,
        f"{{{package_rel_ns}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{office_rel_ns}/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )
    content_types = Element(f"{{{content_types_ns}}}Types")
    SubElement(
        content_types,
        f"{{{content_types_ns}}}Default",
        {
            "Extension": "rels",
            "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
        },
    )
    SubElement(
        content_types,
        f"{{{content_types_ns}}}Default",
        {"Extension": "xml", "ContentType": "application/xml"},
    )
    SubElement(
        content_types,
        f"{{{content_types_ns}}}Override",
        {
            "PartName": "/xl/workbook.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        },
    )
    SubElement(
        content_types,
        f"{{{content_types_ns}}}Override",
        {
            "PartName": "/xl/worksheets/sheet1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        },
    )

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", tostring(content_types, encoding="utf-8", xml_declaration=True))
        archive.writestr("_rels/.rels", tostring(root_relationships, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/workbook.xml", tostring(workbook, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/_rels/workbook.xml.rels", tostring(workbook_relationships, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/worksheets/sheet1.xml", tostring(worksheet, encoding="utf-8", xml_declaration=True))
    return output.getvalue()


@router.get("/audit-logs")
def list_admin_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    user_id: UUID | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    query = _filtered_audit_log_query(
        db, action, entity_type, user_id, start_date, end_date
    )

    # --------------------------------------------------------
    # Count matching records before pagination
    # --------------------------------------------------------

    total = query.count()

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    logs = (
        query
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

        # Fetch names for users associated with the current page.
    user_ids = {
        log.user_id
        for log in logs
        if log.user_id is not None
    }

    users_by_id = {}

    if user_ids:
        users = (
            db.query(User)
            .filter(User.id.in_(user_ids))
            .all()
        )

        users_by_id = {
            user.id: user.full_name
            for user in users
        }

    return {
        "items": [
            {
                "id": str(log.id),
                    "user_id": (
                    str(log.user_id)
                    if log.user_id
                    else None
                ),
                "user_name": (
                    users_by_id.get(log.user_id)
                    if log.user_id
                    else None
                ),
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": (
                    str(log.entity_id)
                    if log.entity_id
                    else None
                ),
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": (
                    str(log.ip_address)
                    if log.ip_address
                    else None
                ),
                "created_at": (
                    log.created_at.isoformat()
                    if log.created_at
                    else None
                ),
            }
            for log in logs
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (
                (total + page_size - 1) // page_size
            ),
        },
    }


@router.get("/audit-logs/export")
def export_admin_audit_logs(
    format: str = Query(..., pattern="^(csv|xlsx|pdf)$"),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    user_id: UUID | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    logs = (
        _filtered_audit_log_query(
            db, action, entity_type, user_id, start_date, end_date
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .all()
    )
    headers = [
        "ID",
        "Time",
        "Action",
        "Entity Type",
        "Entity ID",
        "User",
        "IP Address",
        "Old Values",
        "New Values",
    ]
    rows = _audit_log_export_rows(db, logs)
    filename = f"audit-logs.{format}"

    if format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(
                [
                    f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value
                    for value in row
                ]
            )
        return Response(
            output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format == "xlsx":
        return Response(
            _build_audit_log_xlsx(headers, rows),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from xml.sax.saxutils import escape

    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A3),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Audit Logs",
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    cell_style = ParagraphStyle(
        "AuditCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=6,
        leading=7.5,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    table_data = [
        [Paragraph(escape(header), cell_style) for header in headers],
        *[
            [Paragraph(escape(value or "—"), cell_style) for value in row]
            for row in rows
        ],
    ]
    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[35 * mm, 31 * mm, 31 * mm, 24 * mm, 35 * mm, 30 * mm, 22 * mm, 58 * mm, 58 * mm],
        splitByRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#174b70")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef5fa")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cedbe5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    document.build(
        [
            Paragraph("Audit Logs", title_style),
            Paragraph(f"{len(rows)} matching events", styles["Normal"]),
            Spacer(1, 5 * mm),
            table,
        ]
    )
    return Response(
        pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================
# GET ONE AUDIT LOG
# GET /admin/audit-logs/{log_id}
# ============================================================

@router.get("/audit-logs/{log_id}")
def get_admin_audit_log(
    log_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    log = (
        db.query(AuditLog)
        .filter(
            AuditLog.id == log_id
        )
        .first()
    )

    if not log:
        raise HTTPException(
            status_code=404,
            detail="Audit log not found.",
        )

    return {
        "id": str(log.id),
        "user_id": (
            str(log.user_id)
            if log.user_id
            else None
        ),
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": (
            str(log.entity_id)
            if log.entity_id
            else None
        ),
        "old_values": log.old_values,
        "new_values": log.new_values,
        "ip_address": (
            str(log.ip_address)
            if log.ip_address
            else None
        ),
        "created_at": (
            log.created_at.isoformat()
            if log.created_at
            else None
        ),
    }


@router.post(
    "/references",
    response_model=ReferenceDocumentResponse,
)
async def add_reference(
    title: str = Form(...),
    document_type: str = Form("FTER"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="File is required.",
        )

    extension = Path(file.filename).suffix.lower()
    safe_filename = f"{uuid4()}{extension}"

    upload_directory = (
        Path(settings.upload_dir)
        / "reference_documents"
    )
    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = upload_directory / safe_filename

    try:
        file_size, sha256_hash = await save_reference_file(
            file,
            destination,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    existing = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.sha256_hash == sha256_hash,
            ReferenceDocument.status != "DELETED",
        )
        .first()
    )

    if existing:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail=(
                "This document already exists "
                "in the reference database."
            ),
        )

    reference = ReferenceDocument(
        title=title,
        document_type=document_type,
        file_name=file.filename,
        file_path=str(destination),
        file_size=file_size,
        mime_type=file.content_type,
        sha256_hash=sha256_hash,
        status="ACTIVE",
        current_version=1,
        added_by=current_user.id,
        approved_by=current_user.id,
        approved_at=datetime.now(timezone.utc),
    )

    try:
        db.add(reference)
        db.flush()

        version = ReferenceDocumentVersion(
            reference_document_id=reference.id,
            version_number=1,
            file_name=file.filename,
            file_path=str(destination),
            sha256_hash=sha256_hash,
            uploaded_by=current_user.id,
            approved_by=current_user.id,
            approved_at=datetime.now(timezone.utc),
            change_reason="Initial reference upload",
        )
        db.add(version)

        create_audit_log(
            db,
            user_id=current_user.id,
            action="REFERENCE_CREATED",
            entity_type="REFERENCE_DOCUMENT",
            entity_id=reference.id,
            new_values={
                "title": title,
                "document_type": document_type,
                "file_name": file.filename,
                "version": 1,
            },
        )

        db.commit()
        db.refresh(reference)

    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise

    reference_id = str(reference.id)

    # Automatically index the newly uploaded reference.
    try:
        sentence_count = index_reference_document(
            db=db,
            reference_document=reference,
        )
    except Exception as exc:
        db.rollback()
        print(
            "Automatic reference indexing failed "
            f"for {reference_id}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Reference uploaded successfully, but indexing "
                f"failed. Reference ID: {reference_id}. "
                "Check backend logs and retry using the Admin "
                "Index Reference endpoint."
            ),
        )

    # Record the automatic indexing event.
    try:
        create_audit_log(
            db,
            user_id=current_user.id,
            action="REFERENCE_INDEXED",
            entity_type="REFERENCE_DOCUMENT",
            entity_id=reference.id,
            new_values={
                "version": reference.current_version,
                "sentence_count": sentence_count,
                "trigger": "AUTOMATIC_UPLOAD",
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        print(
            "Warning: reference indexing succeeded, but "
            f"its audit record failed for {reference_id}: {exc}"
        )

    db.refresh(reference)

    return ReferenceDocumentResponse(
        id=str(reference.id),
        title=reference.title,
        document_type=reference.document_type,
        file_name=reference.file_name,
        file_size=reference.file_size,
        mime_type=reference.mime_type,
        sha256_hash=reference.sha256_hash,
        status=reference.status,
        current_version=reference.current_version,
        added_by=(
            str(reference.added_by)
            if reference.added_by
            else None
        ),
        approved_by=(
            str(reference.approved_by)
            if reference.approved_by
            else None
        ),
    )


from sqlalchemy import func


@router.get("/dashboard")
def get_admin_dashboard(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    """Return date-filtered statistics for the Admin Dashboard."""

    if days not in (7, 30, 90, 365):
        raise HTTPException(
            status_code=400,
            detail="days must be one of: 7, 30, 90, 365",
        )

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days - 1)

    # Apply the selected date range to scans.
    period_scans = db.query(Scan).filter(
        Scan.created_at >= start_date,
        Scan.created_at <= now,
    )

    total_documents = period_scans.count()

    processing_scans = period_scans.filter(
        Scan.status == "PROCESSING"
    ).count()

    completed_scans = period_scans.filter(
        Scan.status == "COMPLETED"
    ).count()

    failed_scans = period_scans.filter(
        Scan.status == "FAILED"
    ).count()

    # User count is an overall count, not restricted to the scan period.
    total_users = db.query(func.count(User.id)).scalar() or 0

    # Count analyses associated with scans in the selected period.
    period_analyses = (
        db.query(PlagiarismAnalysis)
        .join(Scan, Scan.id == PlagiarismAnalysis.scan_id)
        .filter(
            Scan.created_at >= start_date,
            Scan.created_at <= now,
        )
    )

    pending_analyses = period_analyses.filter(
        PlagiarismAnalysis.status == "PROCESSING"
    ).count()

    average_similarity = (
        period_analyses
        .with_entities(func.avg(PlagiarismAnalysis.overall_similarity))
        .scalar()
    )

    average_plagiarism_score = (
        round(float(average_similarity) * 100, 2)
        if average_similarity is not None
        else None
    )

    pending_reference_requests = (
        db.query(func.count(DocumentRequestModel.id))
        .filter(DocumentRequestModel.status == "PENDING")
        .scalar()
        or 0
    )

    # Daily scan counts for the selected period.
    daily_rows = (
        period_scans
        .with_entities(
            func.date(Scan.created_at).label("scan_date"),
            func.count(Scan.id).label("scan_count"),
        )
        .group_by(func.date(Scan.created_at))
        .order_by(func.date(Scan.created_at))
        .all()
    )

    date_wise_scans = [
        {
            "date": row.scan_date.isoformat(),
            "count": int(row.scan_count),
        }
        for row in daily_rows
    ]

    # Daily average plagiarism similarity, expressed as a percentage.
    similarity_rows = (
        db.query(
            func.date(Scan.created_at).label("scan_date"),
            func.avg(
                PlagiarismAnalysis.overall_similarity
            ).label("average_score"),
        )
        .join(
            PlagiarismAnalysis,
            PlagiarismAnalysis.scan_id == Scan.id,
        )
        .filter(
            Scan.created_at >= start_date,
            Scan.created_at <= now,
            PlagiarismAnalysis.overall_similarity.isnot(None),
        )
        .group_by(func.date(Scan.created_at))
        .order_by(func.date(Scan.created_at))
        .all()
    )

    similarity_trend = [
        {
            "date": row.scan_date.isoformat(),
            "average_score": round(float(row.average_score) * 100, 2),
        }
        for row in similarity_rows
    ]

    period_scan_dates = (
        period_scans
        .with_entities(Scan.id, Scan.created_at)
        .all()
    )
    classifier_by_scan = latest_classifier_results_by_scan(
        db,
        [scan_id for scan_id, _ in period_scan_dates],
    )
    ai_scores_by_date: dict[str, list[float]] = {}
    for scan_id, created_at in period_scan_dates:
        classifier = classifier_by_scan.get(scan_id)
        if (
            classifier is None
            or classifier.status != "COMPLETED"
            or classifier.score is None
            or created_at is None
        ):
            continue
        ai_scores_by_date.setdefault(created_at.date().isoformat(), []).append(
            float(classifier.score)
        )

    all_ai_scores = [
        score
        for scores in ai_scores_by_date.values()
        for score in scores
    ]
    average_ai_score = (
        round(sum(all_ai_scores) / len(all_ai_scores), 2)
        if all_ai_scores
        else None
    )
    ai_score_trend = [
        {
            "date": date,
            "average_score": round(sum(scores) / len(scores), 2),
        }
        for date, scores in sorted(ai_scores_by_date.items())
    ]

    # Role distribution: number of users assigned to each role.
    role_rows = (
        db.query(
            Role.role_name,
            func.count(UserRole.user_id.distinct()),
        )
        .join(UserRole, UserRole.role_id == Role.id)
        .join(User, User.id == UserRole.user_id)
        .filter(User.status == "ACTIVE")
        .group_by(Role.role_name)
        .order_by(Role.role_name)
        .all()
    )

    user_role_distribution = [
        {"name": role_name, "value": int(user_count)}
        for role_name, user_count in role_rows
    ]

    # Scan processing status distribution for the selected period.
    status_rows = (
        period_scans
        .with_entities(
            Scan.status,
            func.count(Scan.id),
        )
        .group_by(Scan.status)
        .order_by(Scan.status)
        .all()
    )

    document_status_distribution = [
        {"name": scan_status, "value": int(count)}
        for scan_status, count in status_rows
    ]

    # Department and location fields are not present in the Scan model.
    department_submissions = []
    department_similarity_scores = []
    department_ai_scores = []
    organization_locations = []

    # Recent scans, with the latest analysis score for each scan.
    recent_scan_rows = (
        period_scans
        .order_by(Scan.created_at.desc())
        .limit(10)
        .all()
    )

    recent_scans = []

    for scan in recent_scan_rows:
        latest_analysis = (
            db.query(PlagiarismAnalysis)
            .filter(PlagiarismAnalysis.scan_id == scan.id)
            .order_by(
                PlagiarismAnalysis.created_at.desc(),
                PlagiarismAnalysis.id.desc(),
            )
            .first()
        )

        plagiarism_score = None
        if (
            latest_analysis is not None
            and latest_analysis.overall_similarity is not None
        ):
            plagiarism_score = round(
                float(latest_analysis.overall_similarity) * 100,
                2,
            )

        classifier = classifier_by_scan.get(scan.id)
        recent_scans.append(
            {
                "id": str(scan.id),
                "title": scan.title,
                "file_name": scan.file_name,
                "mime_type": scan.mime_type,
                "department": None,
                "status": scan.status,
                "plagiarism_score": plagiarism_score,
                "ai_score": (
                    float(classifier.score)
                    if classifier is not None
                    and classifier.status == "COMPLETED"
                    and classifier.score is not None
                    else None
                ),
                "ai_confidence": (
                    classifier_model_confidence(classifier)
                    if classifier is not None and classifier.status == "COMPLETED"
                    else None
                ),
                "ai_status": (
                    classifier.status if classifier is not None else "NOT_AVAILABLE"
                ),
                "created_at": (
                    scan.created_at.isoformat()
                    if scan.created_at
                    else None
                ),
            }
        )

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "total_documents": total_documents,
            "total_users": total_users,
            "average_plagiarism_score": average_plagiarism_score,
            "average_ai_score": average_ai_score,
            "pending_analyses": pending_analyses,
            "completed_scans": completed_scans,
            "failed_scans": failed_scans,
            "pending_reference_requests": pending_reference_requests,
        },
        "date_wise_scans": date_wise_scans,
        "similarity_trend": similarity_trend,
        "ai_score_trend": ai_score_trend,
        "department_submissions": department_submissions,
        "department_similarity_scores": department_similarity_scores,
        "department_ai_scores": department_ai_scores,
        "document_status_distribution": document_status_distribution,
        "user_role_distribution": user_role_distribution,
        "organization_locations": organization_locations,
        "recent_scans": recent_scans,
    }
