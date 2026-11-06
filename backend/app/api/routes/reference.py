from pathlib import Path
import shutil
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.config import settings
from app.db.database import get_db

from app.models.plagiarism import DocumentRequest
from app.models.reference import (
    ReferenceDocument,
    ReferenceDocumentVersion,
)
from app.models.scan import Scan
from app.models.user import User

from app.schemas.reference import (
    CreateReferenceAddRequestResponse,
    CreateReferenceRequestPayload,
    ReferenceDocumentResponse,
    ReferenceRequestResponse,
    ReferenceIndexResponse,
)

from app.services.audit_service import create_audit_log
from app.services.reference_service import save_reference_file
from app.services.reference_index_service import index_reference_document
from app.services.document_extraction_service import extract_document


router = APIRouter(
    prefix="/reference",
    tags=["Reference Database"],
)


# ============================================================
# LIST REFERENCES
# ============================================================

@router.get(
    "",
    response_model=list[ReferenceDocumentResponse],
)
def list_references(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    references = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.status == "ACTIVE"
        )
        .order_by(
            ReferenceDocument.created_at.desc()
        )
        .all()
    )

    return [
        ReferenceDocumentResponse(
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
            created_at=reference.created_at.isoformat(),
        )
        for reference in references
    ]


@router.get("/{reference_id}/document")
def view_reference_document(
    reference_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    reference = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.id == reference_id,
            ReferenceDocument.status == "ACTIVE",
        )
        .first()
    )

    if reference is None:
        raise HTTPException(
            status_code=404,
            detail="Reference document not found.",
        )

    extension = Path(reference.file_name).suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    media_type = media_types.get(
        extension,
        reference.mime_type or "application/octet-stream",
    )

    file_path = Path(reference.file_path).resolve()
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Reference document file not found.",
        )

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=reference.file_name,
        content_disposition_type=(
            "inline" if extension in {".pdf", ".txt"} else "attachment"
        ),
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{reference_id}/preview", response_class=PlainTextResponse)
def preview_reference_document(
    reference_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    reference = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.id == reference_id,
            ReferenceDocument.status == "ACTIVE",
        )
        .first()
    )
    if reference is None:
        raise HTTPException(
            status_code=404,
            detail="Reference document not found.",
        )

    file_path = Path(reference.file_path).resolve()
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Reference document file not found.",
        )
    if file_path.suffix.lower() != ".docx":
        raise HTTPException(
            status_code=415,
            detail="Text extraction preview is only available for DOCX files.",
        )

    pages = extract_document(file_path)
    text = "\n\n".join(page.raw_text for page in pages)
    return PlainTextResponse(
        text,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{reference_id}", status_code=204)
def delete_reference_document(
    reference_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    reference = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.id == reference_id,
            ReferenceDocument.status != "DELETED",
        )
        .first()
    )

    if reference is None:
        raise HTTPException(
            status_code=404,
            detail="Reference document not found.",
        )

    previous_status = reference.status
    reference.status = "DELETED"
    reference.updated_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        user_id=current_user.id,
        action="REFERENCE_DELETED",
        entity_type="REFERENCE_DOCUMENT",
        entity_id=reference.id,
        old_values={
            "title": reference.title,
            "status": previous_status,
            "current_version": reference.current_version,
        },
        new_values={
            "status": "DELETED",
            "file_retained": True,
        },
    )

    db.commit()


# ============================================================
# ADD REFERENCE
# ============================================================


@router.post(
    "",
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


# ============================================================
# INDEX REFERENCE DOCUMENT
# ============================================================

@router.post(
    "/{reference_id}/index",
    response_model=ReferenceIndexResponse,
)
def index_reference(
    reference_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    """
    Index a reference document for plagiarism detection.

    Pipeline:

        Reference Document
                |
                v
        Extract document
                |
                v
        Normalize text
                |
                v
        Split sentences
                |
                v
        reference_sentences
                |
                v
        N-gram fingerprints
                |
                v
        Qwen3 embeddings
                |
                v
        pgvector
    """

    # --------------------------------------------------------
    # Validate UUID
    # --------------------------------------------------------

    try:
        reference_uuid = UUID(reference_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid reference_id.",
        )

    # --------------------------------------------------------
    # Find reference
    # --------------------------------------------------------

    reference = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.id == reference_uuid,
            ReferenceDocument.status != "DELETED",
        )
        .first()
    )

    if not reference:
        raise HTTPException(
            status_code=404,
            detail="Reference document not found.",
        )

    # --------------------------------------------------------
    # Verify current version exists
    # --------------------------------------------------------

    current_version = (
        db.query(ReferenceDocumentVersion)
        .filter(
            ReferenceDocumentVersion.reference_document_id
            == reference.id,
            ReferenceDocumentVersion.version_number
            == reference.current_version,
        )
        .first()
    )

    if not current_version:
        raise HTTPException(
            status_code=404,
            detail=(
                "Current reference document version "
                "was not found."
            ),
        )

    # --------------------------------------------------------
    # Verify physical file exists
    # --------------------------------------------------------

    file_path = Path(
        current_version.file_path
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Reference document file was not found "
                f"at: {file_path}"
            ),
        )

    # --------------------------------------------------------
    # Run indexing pipeline
    # --------------------------------------------------------

    try:
        sentence_count = index_reference_document(
            db=db,
            reference_document=reference,
        )

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Reference indexing failed: "
                f"{str(exc)}"
            ),
        )

    # --------------------------------------------------------
    # Count embeddings after indexing
    # --------------------------------------------------------

    from app.models.reference import ReferenceSentence
    from app.models.reference import ReferenceEmbedding

    embedding_count = (
        db.query(ReferenceEmbedding)
        .join(
            ReferenceSentence,
            ReferenceEmbedding.sentence_id
            == ReferenceSentence.id,
        )
        .filter(
            ReferenceSentence.reference_document_id
            == reference.id,
        )
        .count()
    )

    # --------------------------------------------------------
    # Audit log
    # --------------------------------------------------------

    create_audit_log(
        db,
        user_id=current_user.id,
        action="REFERENCE_INDEXED",
        entity_type="REFERENCE_DOCUMENT",
        entity_id=reference.id,
        new_values={
            "version": reference.current_version,
            "sentence_count": sentence_count,
            "embedding_count": embedding_count,
        },
    )

    db.commit()

    return {
        "reference_id": str(reference.id),
        "title": reference.title,
        "version": reference.current_version,
        "status": "INDEXED",
        "sentence_count": sentence_count,
        "embedding_count": embedding_count,
    }


# ============================================================
# CREATE REFERENCE VERSION
# ============================================================

@router.post(
    "/{reference_id}/versions",
    response_model=ReferenceDocumentResponse,
)
async def create_reference_version(
    reference_id: str,
    file: UploadFile = File(...),
    change_reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    reference = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.id == reference_id,
            ReferenceDocument.status != "DELETED",
        )
        .first()
    )

    if not reference:
        raise HTTPException(
            status_code=404,
            detail="Reference document not found.",
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="File is required.",
        )

    extension = Path(file.filename).suffix.lower()

    new_version_number = (
        reference.current_version + 1
    )

    safe_filename = (
        f"{uuid4()}_v{new_version_number}{extension}"
    )

    upload_directory = (
        Path(settings.upload_dir)
        / "reference_documents"
    )

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        upload_directory / safe_filename
    )

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

    # --------------------------------------------------------
    # Prevent uploading the exact same content
    # as the existing current version.
    # --------------------------------------------------------

    if sha256_hash == reference.sha256_hash:
        destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=409,
            detail=(
                "The uploaded file is identical "
                "to the current reference version."
            ),
        )

    version = ReferenceDocumentVersion(
    reference_document_id=reference.id,
    version_number=1,
    file_name=file.filename,
    file_path=str(destination),
    mime_type=file.content_type,
    sha256_hash=sha256_hash,
    uploaded_by=current_user.id,
    approved_by=current_user.id,
    approved_at=datetime.now(timezone.utc),
)
    db.add(version)

    old_version = reference.current_version

    reference.current_version = new_version_number
    reference.file_name = file.filename
    reference.file_path = str(destination)
    reference.file_size = file_size
    reference.mime_type = file.content_type
    reference.sha256_hash = sha256_hash
    reference.approved_by = current_user.id
    reference.approved_at = datetime.now(timezone.utc)
    reference.updated_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        user_id=current_user.id,
        action="REFERENCE_VERSION_CREATED",
        entity_type="REFERENCE_DOCUMENT",
        entity_id=reference.id,
        old_values={
            "version": old_version,
        },
        new_values={
            "version": new_version_number,
            "file_name": file.filename,
            "change_reason": change_reason,
        },
    )

    db.commit()
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


# ============================================================
# LIST REFERENCE VERSIONS
# ============================================================

@router.get("/{reference_id}/versions")
def list_reference_versions(
    reference_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):
    reference = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.id == reference_id
        )
        .first()
    )

    if not reference:
        raise HTTPException(
            status_code=404,
            detail="Reference document not found.",
        )

    versions = (
        db.query(ReferenceDocumentVersion)
        .filter(
            ReferenceDocumentVersion.reference_document_id
            == reference.id
        )
        .order_by(
            ReferenceDocumentVersion.version_number.desc()
        )
        .all()
    )

    return [
        {
            "id": str(version.id),
            "version_number": version.version_number,
            "file_name": version.file_name,
            "file_size": version.file_size,
            "mime_type": version.mime_type,
            "sha256_hash": version.sha256_hash,
            "uploaded_by": (
                str(version.uploaded_by)
                if version.uploaded_by
                else None
            ),
            "approved_by": (
                str(version.approved_by)
                if version.approved_by
                else None
            ),
            "approved_at": version.approved_at,
            "change_reason": version.change_reason,
            "created_at": version.created_at,
        }
        for version in versions
    ]


# ============================================================
# CREATE REFERENCE REQUEST
# ============================================================

@router.post(
    "/requests",
    response_model=ReferenceRequestResponse,
)
def create_reference_request(
    request: CreateReferenceRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("INSTRUCTOR")
    ),
):
    if request.request_type in {"UPDATE", "DELETE"}:
        if not request.reference_document_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "reference_document_id is required "
                    "for UPDATE or DELETE requests"
                ),
            )

        reference = (
            db.query(ReferenceDocument)
            .filter(
                ReferenceDocument.id
                == request.reference_document_id,
                ReferenceDocument.status != "DELETED",
            )
            .first()
        )

        if not reference:
            raise HTTPException(
                status_code=404,
                detail="Reference document not found",
            )

    if request.request_type == "ADD":
        reference_document_id = None

    else:
        reference_document_id = UUID(
            request.reference_document_id
        )

    new_request = DocumentRequest(
        request_type=request.request_type,
        requested_by=current_user.id,
        reference_document_id=reference_document_id,
        title=request.title,
        reason=request.reason,
        status="PENDING",
    )

    db.add(new_request)

    db.flush()

    create_audit_log(
        db,
        user_id=current_user.id,
        action="REFERENCE_REQUEST_CREATED",
        entity_type="DOCUMENT_REQUEST",
        entity_id=new_request.id,
        new_values={
            "request_type": request.request_type,
            "title": request.title,
        },
    )

    db.commit()
    db.refresh(new_request)

    return ReferenceRequestResponse(
        id=str(new_request.id),
        request_type=new_request.request_type,
        requested_by=str(new_request.requested_by),
        reference_document_id=(
            str(new_request.reference_document_id)
            if new_request.reference_document_id
            else None
        ),
        title=new_request.title,
        reason=new_request.reason,
        status=new_request.status,
        reviewed_by=(
            str(new_request.reviewed_by)
            if new_request.reviewed_by
            else None
        ),
        reviewed_at=(
            new_request.reviewed_at.isoformat()
            if new_request.reviewed_at
            else None
        ),
        rejection_reason=new_request.rejection_reason,
        admin_comments=new_request.admin_comments,
        created_at=new_request.created_at.isoformat(),
    )


# ============================================================
# GET MY REFERENCE REQUESTS
# ============================================================

@router.get(
    "/requests/my",
    response_model=list[ReferenceRequestResponse],
)
def get_my_reference_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("INSTRUCTOR")
    ),
):
    requests = (
        db.query(DocumentRequest)
        .filter(
            DocumentRequest.requested_by
            == current_user.id
        )
        .order_by(
            DocumentRequest.created_at.desc()
        )
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
            scan_id=str(item.scan_id) if item.scan_id else None,
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
        )
        for item in requests
    ]


# ============================================================
# CREATE REFERENCE ADD REQUEST
# ============================================================

@router.post(
    "/requests/scans/{scan_id}",
    response_model=CreateReferenceAddRequestResponse,
)
def create_reference_scan_request(
    scan_id: UUID,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("INSTRUCTOR")
    ),
):
    reason = reason.strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="Reason is required",
        )

    scan = (
        db.query(Scan)
        .filter(Scan.id == scan_id)
        .first()
    )
    if not scan:
        raise HTTPException(
            status_code=404,
            detail="Scanned document not found",
        )

    if (scan.owner_id or scan.scanned_by) != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to request this scanned document",
        )

    extension = Path(scan.file_name).suffix.lower()
    if extension not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX and TXT files can be requested",
        )

    source_path = Path(scan.file_path)
    if not source_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Original scanned document file not found",
        )

    existing_reference = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.sha256_hash == scan.sha256_hash,
            ReferenceDocument.status != "DELETED",
        )
        .first()
    )
    if existing_reference:
        raise HTTPException(
            status_code=409,
            detail="This document already exists in the Document Manager",
        )

    existing_request = (
        db.query(DocumentRequest)
        .filter(
            DocumentRequest.requested_by == current_user.id,
            DocumentRequest.request_type == "ADD",
            DocumentRequest.status == "PENDING",
            DocumentRequest.title == scan.title,
        )
        .first()
    )
    if existing_request:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending ADD request with this title",
        )

    generated_filename = f"{uuid4()}{extension}"
    destination = (
        Path(settings.upload_dir)
        / "reference_requests"
        / generated_filename
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source_path, destination)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not prepare the scanned document for review",
        ) from exc

    new_request = DocumentRequest(
        request_type="ADD",
        requested_by=current_user.id,
        reference_document_id=None,
        scan_id=scan.id,
        title=scan.title,
        reason=reason,
        status="PENDING",
        admin_comments=(
            f"FILE_PATH={destination}\n"
            f"FILE_NAME={scan.file_name}\n"
            f"FILE_SIZE={scan.file_size}\n"
            f"MIME_TYPE={scan.mime_type}\n"
            f"SHA256={scan.sha256_hash}"
        ),
    )
    db.add(new_request)
    db.flush()

    create_audit_log(
        db,
        user_id=current_user.id,
        action="REFERENCE_ADD_REQUEST_CREATED",
        entity_type="DOCUMENT_REQUEST",
        entity_id=new_request.id,
        new_values={
            "request_type": "ADD",
            "title": scan.title,
            "scan_id": str(scan.id),
            "file_name": scan.file_name,
            "sha256_hash": scan.sha256_hash,
        },
    )

    db.commit()
    db.refresh(new_request)

    return CreateReferenceAddRequestResponse(
        id=str(new_request.id),
        request_type=new_request.request_type,
        title=new_request.title,
        reason=new_request.reason,
        status=new_request.status,
        pending_file_name=scan.file_name,
        created_at=new_request.created_at.isoformat(),
    )


@router.post(
    "/requests/add",
    response_model=CreateReferenceAddRequestResponse,
)
async def create_reference_add_request(
    title: str = Form(...),
    reason: str = Form(...),
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("INSTRUCTOR")
    ),
):
    if not title.strip():
        raise HTTPException(
            status_code=400,
            detail="Title is required",
        )

    if not reason.strip():
        raise HTTPException(
            status_code=400,
            detail="Reason is required",
        )

    if not document.filename:
        raise HTTPException(
            status_code=400,
            detail="Document filename is required",
        )

    # --------------------------------------------------
    # Check file extension
    # --------------------------------------------------

    original_extension = Path(
        document.filename
    ).suffix.lower()

    allowed_extensions = {
        ".pdf",
        ".docx",
        ".txt",
    }

    if original_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX and TXT files are allowed",
        )

    # --------------------------------------------------
    # Generate safe server-side filename
    # --------------------------------------------------

    generated_filename = (
        f"{uuid4()}{original_extension}"
    )

    destination = (
        Path(settings.upload_dir)
        / "reference_requests"
        / generated_filename
    )

    try:
        file_size, sha256_hash = await save_reference_file(
            document,
            destination,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # --------------------------------------------------
    # Prevent duplicate reference documents
    # --------------------------------------------------

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
        destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=409,
            detail=(
                "This document already exists in "
                "the reference database."
            ),
        )

    # --------------------------------------------------
    # Prevent duplicate pending requests
    # --------------------------------------------------

    existing_request = (
        db.query(DocumentRequest)
        .filter(
            DocumentRequest.requested_by
            == current_user.id,
            DocumentRequest.request_type == "ADD",
            DocumentRequest.status == "PENDING",
            DocumentRequest.title == title.strip(),
        )
        .first()
    )

    if existing_request:
        destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=409,
            detail=(
                "You already have a pending ADD request "
                "with this title."
            ),
        )

    # --------------------------------------------------
    # Store file information in request
    # --------------------------------------------------

    new_request = DocumentRequest(
        request_type="ADD",
        requested_by=current_user.id,
        reference_document_id=None,
        scan_id=None,
        title=title.strip(),
        reason=reason.strip(),
        status="PENDING",
    )

    # Store pending-file metadata in admin_comments temporarily
    new_request.admin_comments = (
        f"FILE_PATH={destination}\n"
        f"FILE_NAME={document.filename}\n"
        f"FILE_SIZE={file_size}\n"
        f"MIME_TYPE={document.content_type or 'application/octet-stream'}\n"
        f"SHA256={sha256_hash}"
    )

    db.add(new_request)

    db.flush()

    create_audit_log(
        db,
        user_id=current_user.id,
        action="REFERENCE_ADD_REQUEST_CREATED",
        entity_type="DOCUMENT_REQUEST",
        entity_id=new_request.id,
        new_values={
            "request_type": "ADD",
            "title": title.strip(),
            "file_name": document.filename,
            "sha256_hash": sha256_hash,
        },
    )

    db.commit()
    db.refresh(new_request)

    return CreateReferenceAddRequestResponse(
        id=str(new_request.id),
        request_type=new_request.request_type,
        title=new_request.title,
        reason=new_request.reason,
        status=new_request.status,
        pending_file_name=document.filename,
        created_at=new_request.created_at.isoformat(),
    )
