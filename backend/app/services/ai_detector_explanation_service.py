from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import AIDetectorResult
from app.models.ai_detector_explanation import AIDetectorExplanation


ALLOWED_DETECTOR_STATUSES = {
    "COMPLETED",
    "FAILED",
    "NOT_CONFIGURED",
    "NOT_ANALYZED",
}

EXPLANATION_STATUSES = {
    "PROCESSING",
    "COMPLETED",
    "FAILED",
}


def create_explanation_record(
    db: Session,
    *,
    detector_result_id: UUID,
    model_name: str,
    prompt_version: str,
    generation_metadata: dict | None = None,
) -> AIDetectorExplanation:
    """
    Create a new explanation-generation record.

    The caller owns the transaction. This function only flushes.
    It never commits or rolls back.
    """

    if not model_name.strip():
        raise ValueError("Model name cannot be empty.")

    if not prompt_version.strip():
        raise ValueError("Prompt version cannot be empty.")

    detector_result = (
        db.query(AIDetectorResult)
        .filter(AIDetectorResult.id == detector_result_id)
        .first()
    )

    if detector_result is None:
        raise ValueError(
            f"Detector result not found: {detector_result_id}"
        )

    if detector_result.status not in ALLOWED_DETECTOR_STATUSES:
        raise ValueError(
            "Cannot explain a detector result that is not terminal. "
            f"Current status: {detector_result.status}"
        )

    record = AIDetectorExplanation(
        detector_result_id=detector_result_id,
        model_name=model_name.strip(),
        prompt_version=prompt_version.strip(),
        status="PROCESSING",
        generation_metadata=generation_metadata or {},
    )

    db.add(record)
    db.flush()

    return record


def complete_explanation(
    db: Session,
    *,
    explanation_id: UUID,
    explanation_text: str,
    generation_metadata: dict | None = None,
) -> AIDetectorExplanation:
    """Save a successful explanation."""

    if not explanation_text.strip():
        raise ValueError("Explanation text cannot be empty.")

    record = get_explanation(
        db,
        explanation_id=explanation_id,
    )

    if record.status != "PROCESSING":
        raise ValueError(
            f"Cannot complete explanation with status: {record.status}"
        )

    record.status = "COMPLETED"
    record.explanation_text = explanation_text.strip()
    record.error_message = None
    record.completed_at = datetime.now(timezone.utc)

    if generation_metadata:
        record.generation_metadata = {
            **(record.generation_metadata or {}),
            **generation_metadata,
        }

    db.flush()
    return record


def fail_explanation(
    db: Session,
    *,
    explanation_id: UUID,
    error_message: str,
) -> AIDetectorExplanation:
    """Mark explanation generation as failed."""

    if not error_message.strip():
        raise ValueError("Error message cannot be empty.")

    record = get_explanation(
        db,
        explanation_id=explanation_id,
    )

    if record.status != "PROCESSING":
        raise ValueError(
            f"Cannot fail explanation with status: {record.status}"
        )

    record.status = "FAILED"
    record.error_message = error_message.strip()
    record.explanation_text = None
    record.completed_at = datetime.now(timezone.utc)

    db.flush()
    return record


def get_explanation(
    db: Session,
    *,
    explanation_id: UUID,
) -> AIDetectorExplanation:
    """Retrieve one explanation by ID."""

    record = (
        db.query(AIDetectorExplanation)
        .filter(AIDetectorExplanation.id == explanation_id)
        .first()
    )

    if record is None:
        raise ValueError(
            f"Explanation record not found: {explanation_id}"
        )

    return record


def get_explanation_history(
    db: Session,
    *,
    detector_result_id: UUID,
) -> list[AIDetectorExplanation]:
    """Retrieve all explanation attempts for a detector result."""

    return (
        db.query(AIDetectorExplanation)
        .filter(
            AIDetectorExplanation.detector_result_id
            == detector_result_id
        )
        .order_by(
            AIDetectorExplanation.created_at.desc(),
            AIDetectorExplanation.id.desc(),
        )
        .all()
    )


def get_latest_completed_explanation(
    db: Session,
    *,
    detector_result_id: UUID,
) -> AIDetectorExplanation | None:
    """Retrieve the latest successfully generated explanation."""

    return (
        db.query(AIDetectorExplanation)
        .filter(
            AIDetectorExplanation.detector_result_id
            == detector_result_id,
            AIDetectorExplanation.status == "COMPLETED",
        )
        .order_by(
            AIDetectorExplanation.completed_at.desc(),
            AIDetectorExplanation.id.desc(),
        )
        .first()
    )
