from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.ai_analysis import AIDetectorResult

from app.services.ai_detector_explanation_generator import (
    PROMPT_VERSION,
    generate_prepared_detector_explanation,
    prepare_detector_explanation,
)

from app.services.ai_detector_explanation_service import (
    create_explanation_record,
    complete_explanation,
    fail_explanation,
    get_explanation,
)


logger = logging.getLogger(__name__)

GENERATION_FAILURE_MESSAGE = (
    "Local explanation generation failed. "
    "Check the Ollama service and application logs."
)


def _serialize_explanation(record: Any) -> dict:
    """Convert an explanation ORM record into an API-safe dictionary."""

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


def _mark_generation_failed(
    explanation_id: UUID,
    *,
    error: Exception,
) -> dict:
    """Persist a failed generation attempt using a fresh session."""

    logger.exception(
        "AI detector explanation generation failed. "
        "Explanation ID: %s",
        explanation_id,
        exc_info=(
            type(error),
            error,
            error.__traceback__,
        ),
    )

    failure_db = SessionLocal()

    try:
        record = fail_explanation(
            failure_db,
            explanation_id=explanation_id,
            error_message=GENERATION_FAILURE_MESSAGE,
        )

        failure_db.commit()
        failure_db.refresh(record)

        return _serialize_explanation(record)

    except Exception:
        failure_db.rollback()

        logger.exception(
            "Could not persist failed explanation status. "
            "Explanation ID: %s",
            explanation_id,
        )

        raise RuntimeError(
            "Explanation generation failed and its failure "
            "status could not be saved."
        ) from error

    finally:
        failure_db.close()


def generate_and_persist_detector_explanation(
    db: Session,
    *,
    detector_result_id: UUID,
) -> dict:
    """
    Generate and persist an on-demand supplementary explanation.

    Workflow:
      1. Validate the completed detector result.
      2. Persist a PROCESSING explanation record.
      3. Prepare prompts using a separate short-lived DB session.
      4. Generate text through local Ollama without a DB session.
      5. Persist COMPLETED or FAILED using a fresh DB session.

    The original detector result is never modified.
    """

    # ---------------------------------------------------------
    # 1. Validate the detector result
    # ---------------------------------------------------------

    detector_result = (
        db.query(AIDetectorResult)
        .filter(
            AIDetectorResult.id == detector_result_id
        )
        .first()
    )

    if detector_result is None:
        raise ValueError(
            f"Detector result not found: {detector_result_id}"
        )

    if detector_result.status != "COMPLETED":
        raise ValueError(
            "Supplementary explanations can only be generated "
            "for completed detector results. "
            f"Current status: {detector_result.status}"
        )

    # ---------------------------------------------------------
    # 2. Create and commit PROCESSING record
    # ---------------------------------------------------------

    try:
        explanation_record = create_explanation_record(
            db,
            detector_result_id=detector_result_id,
            model_name=settings.ollama_model,
            prompt_version=PROMPT_VERSION,
            generation_metadata={
                "generation_source": "LOCAL_OLLAMA",
            },
        )

        explanation_id = explanation_record.id

        # Persist PROCESSING before the potentially long model call.
        db.commit()

    except Exception:
        db.rollback()
        logger.exception(
            "Could not create explanation-generation record "
            "for detector result %s",
            detector_result_id,
        )
        raise

    # ---------------------------------------------------------
    # 3. Prepare prompts using a separate read session
    # ---------------------------------------------------------

    try:
        read_db = SessionLocal()

        try:
            prepared = prepare_detector_explanation(
                read_db,
                detector_result_id=detector_result_id,
            )
        finally:
            read_db.close()

        # -----------------------------------------------------
        # 4. Generate explanation without holding a DB session
        # -----------------------------------------------------

        generated = generate_prepared_detector_explanation(
            prepared
        )

    except Exception as error:
        return _mark_generation_failed(
            explanation_id,
            error=error,
        )

    # ---------------------------------------------------------
    # 5. Persist successful generation
    # ---------------------------------------------------------

    completion_db = SessionLocal()

    try:
        completed_record = complete_explanation(
            completion_db,
            explanation_id=explanation_id,
            explanation_text=generated["explanation_text"],
            generation_metadata=generated["generation_metadata"],
        )

        completion_db.commit()
        completion_db.refresh(completed_record)

        return _serialize_explanation(completed_record)

    except Exception as error:
        completion_db.rollback()

        logger.exception(
            "Could not persist generated explanation. "
            "Explanation ID: %s",
            explanation_id,
        )

        # The completion transaction has been rolled back.
        # Attempt to persist the attempt as FAILED.
        return _mark_generation_failed(
            explanation_id,
            error=error,
        )

    finally:
        completion_db.close()
