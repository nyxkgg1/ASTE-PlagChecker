from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db

from app.models.ai_analysis import (
    AIAnalysisRun,
    AIDetectorResult,
)
from app.models.scan import Scan
from app.models.user import User

from app.services.ai_detector_explanation_orchestrator import (
    generate_and_persist_detector_explanation,
)
from app.services.ai_detector_explanation_service import (
    get_explanation_history,
)


router = APIRouter(
    prefix="/ai-detector-explanations",
    tags=["AI Detector Explanations"],
)


def _get_accessible_detector_result(
    db: Session,
    *,
    detector_result_id: UUID,
    current_user: User,
) -> tuple[AIDetectorResult, Scan]:
    """
    Retrieve a detector result and enforce scan-level authorization.

    ADMIN can access all scans.
    INSTRUCTOR and STUDENT_OFFICER can access their own scans only.
    """

    row = (
        db.query(AIDetectorResult, Scan)
        .join(
            AIAnalysisRun,
            AIDetectorResult.run_id == AIAnalysisRun.id,
        )
        .join(
            Scan,
            AIAnalysisRun.scan_id == Scan.id,
        )
        .filter(
            AIDetectorResult.id == detector_result_id,
        )
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detector result not found.",
        )

    detector_result, scan = row

    roles = {
        user_role.role.role_name
        for user_role in current_user.user_roles
        if user_role.role is not None
    }

    if "ADMIN" in roles:
        return detector_result, scan

    if not roles.intersection(
        {"INSTRUCTOR", "STUDENT_OFFICER"}
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this result.",
        )

    owner_id = scan.owner_id or scan.scanned_by

    if owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this result.",
        )

    return detector_result, scan


def _serialize_history_item(record) -> dict:
    """Convert an explanation record into an API response."""

    return {
        "id": str(record.id),
        "detector_result_id": str(record.detector_result_id),
        "model_name": record.model_name,
        "prompt_version": record.prompt_version,
        "status": record.status,
        "explanation_text": record.explanation_text,
        "error_message": record.error_message,
        "generation_metadata": record.generation_metadata or {},
        "created_at": (
            record.created_at.isoformat()
            if record.created_at
            else None
        ),
        "completed_at": (
            record.completed_at.isoformat()
            if record.completed_at
            else None
        ),
    }


@router.post("/{detector_result_id}/generate")
def generate_explanation(
    detector_result_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate and persist a supplementary explanation for a
    completed AI detector result.
    """

    detector_result, _scan = _get_accessible_detector_result(
        db,
        detector_result_id=detector_result_id,
        current_user=current_user,
    )

    if detector_result.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Supplementary explanations can only be generated "
                "for completed detector results."
            ),
        )

    try:
        return generate_and_persist_detector_explanation(
            db,
            detector_result_id=detector_result_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/detector-results/{detector_result_id}/history")
def explanation_history(
    detector_result_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve all supplementary explanation attempts for a
    detector result, newest first.
    """

    _detector_result, _scan = _get_accessible_detector_result(
        db,
        detector_result_id=detector_result_id,
        current_user=current_user,
    )

    records = get_explanation_history(
        db,
        detector_result_id=detector_result_id,
    )

    return {
        "detector_result_id": str(detector_result_id),
        "count": len(records),
        "items": [
            _serialize_history_item(record)
            for record in records
        ],
    }
