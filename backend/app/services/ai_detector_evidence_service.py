from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import (
    AIAnalysisRun,
    AIDetectorEvidence,
    AIDetectorResult,
)
from app.models.scan import ScanSentence


def _validate_evidence_score(value) -> Decimal | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError("Evidence score must be numeric.")

    try:
        score = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Evidence score must be numeric.") from None

    if not score.is_finite():
        raise ValueError("Evidence score must be finite.")

    if score < Decimal("0") or score > Decimal("100"):
        raise ValueError(
            "Evidence score must be between 0 and 100."
        )

    return score.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def create_detector_evidence(
    db: Session,
    *,
    detector_result_id: UUID,
    sentence_id: UUID,
    evidence_type: str,
    evidence_score=None,
    details: dict | None = None,
) -> AIDetectorEvidence:
    """
    Save evidence for a sentence analyzed by a detector.

    The sentence must belong to the same scan as the detector's
    analysis run.

    The caller owns the transaction. This function flushes but
    never commits or rolls back.
    """

    result = (
        db.query(AIDetectorResult)
        .filter(
            AIDetectorResult.id == detector_result_id
        )
        .first()
    )

    if result is None:
        raise ValueError(
            f"Detector result not found: {detector_result_id}"
        )

    run = (
        db.query(AIAnalysisRun)
        .filter(
            AIAnalysisRun.id == result.run_id
        )
        .first()
    )

    if run is None:
        raise ValueError(
            f"Analysis run not found: {result.run_id}"
        )

    if run.status != "PROCESSING":
        raise ValueError(
            "Evidence cannot be added to a finalized analysis run."
        )

    if result.status in {"NOT_CONFIGURED", "NOT_ANALYZED"}:
        raise ValueError(
            f"Evidence cannot be added to a detector with status: {result.status}"
        )

    if (
        not isinstance(evidence_type, str)
        or not evidence_type.strip()
    ):
        raise ValueError("Evidence type is required.")

    if len(evidence_type.strip()) > 50:
        raise ValueError(
            "Evidence type cannot exceed 50 characters."
        )

    if details is not None and not isinstance(details, dict):
        raise ValueError(
            "Evidence details must be a dictionary or None."
        )

    sentence = (
        db.query(ScanSentence)
        .filter(
            ScanSentence.id == sentence_id
        )
        .first()
    )

    if sentence is None:
        raise ValueError(
            f"Scan sentence not found: {sentence_id}"
        )

    if sentence.scan_id != run.scan_id:
        raise ValueError(
            "Evidence sentence does not belong to the scan "
            "associated with this analysis run."
        )

    score_value = _validate_evidence_score(evidence_score)

    evidence = AIDetectorEvidence(
        detector_result_id=detector_result_id,
        sentence_id=sentence_id,
        evidence_type=evidence_type.strip(),
        evidence_score=score_value,
        details=details,
    )

    db.add(evidence)
    db.flush()

    return evidence


def get_detector_evidence(
    db: Session,
    *,
    detector_result_id: UUID,
) -> list[AIDetectorEvidence]:
    """Retrieve all evidence associated with a detector result."""

    result = (
        db.query(AIDetectorResult)
        .filter(
            AIDetectorResult.id == detector_result_id
        )
        .first()
    )

    if result is None:
        raise ValueError(
            f"Detector result not found: {detector_result_id}"
        )

    return (
        db.query(AIDetectorEvidence)
        .filter(
            AIDetectorEvidence.detector_result_id
            == detector_result_id
        )
        .order_by(
            AIDetectorEvidence.created_at,
            AIDetectorEvidence.id,
        )
        .all()
    )
