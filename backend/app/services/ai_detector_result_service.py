from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import (
    AIAnalysisRun,
    AIDetectorResult,
)
from app.models.model_registry import ModelRegistry


def classifier_model_confidence(result: AIDetectorResult) -> float | None:
    """Return top-class softmax output, deriving it for older classifier rows."""
    if result.confidence is not None:
        return float(result.confidence)
    if result.score is None:
        return None

    ai_probability = float(result.score) / 100
    return max(ai_probability, 1 - ai_probability)


def latest_classifier_results_by_scan(
    db: Session,
    scan_ids: list[UUID],
) -> dict[UUID, AIDetectorResult]:
    """Return each scan's most recent classifier result, in any status."""
    if not scan_ids:
        return {}

    rows = (
        db.query(AIAnalysisRun.scan_id, AIDetectorResult)
        .join(
            AIDetectorResult,
            AIDetectorResult.run_id == AIAnalysisRun.id,
        )
        .filter(
            AIAnalysisRun.scan_id.in_(scan_ids),
            AIDetectorResult.detector_type == "CLASSIFIER",
        )
        .order_by(
            AIAnalysisRun.scan_id.asc(),
            AIAnalysisRun.created_at.desc(),
            AIDetectorResult.created_at.desc(),
            AIAnalysisRun.id.desc(),
        )
        .all()
    )

    latest: dict[UUID, AIDetectorResult] = {}
    for scan_id, result in rows:
        latest.setdefault(scan_id, result)

    return latest


DETECTOR_SEMANTICS = {
    "CLASSIFIER": "AI_LIKELIHOOD_INDICATOR",
    "CORPUS_MATCH": "CORPUS_SIMILARITY",
    "LINGUISTIC_HEURISTIC": "LINGUISTIC_INDICATOR",
    "QWEN_EXPERIMENTAL": None,
}

DETECTOR_STATUSES = {
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "NOT_CONFIGURED",
    "NOT_ANALYZED",
}

TERMINAL_STATUSES = {
    "COMPLETED",
    "FAILED",
    "NOT_CONFIGURED",
    "NOT_ANALYZED",
}


def _to_decimal(
    value,
    *,
    field_name: str,
    minimum: Decimal,
    maximum: Decimal,
    places: str,
) -> Decimal | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field_name} must be numeric.") from None

    if not number.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if number < minimum or number > maximum:
        raise ValueError(
            f"{field_name} must be between {minimum} and {maximum}."
        )

    return number.quantize(
        Decimal(places),
        rounding=ROUND_HALF_UP,
    )


def _validate_detector_inputs(
    *,
    detector_type: str,
    detector_version: str,
    status: str,
    model_id: UUID | None,
    score,
    confidence,
    metrics,
) -> tuple[Decimal | None, Decimal | None, str]:

    if detector_type not in DETECTOR_SEMANTICS:
        raise ValueError(
            f"Unsupported detector type: {detector_type}"
        )
    if detector_type == "QWEN_EXPERIMENTAL" and (
        score is not None or confidence is not None
    ):
        raise ValueError(
            "QWEN_EXPERIMENTAL cannot generate a numerical "
            "authorship score or confidence."
        )
    if not isinstance(detector_version, str) or not detector_version.strip():
        raise ValueError("Detector version is required.")

    if len(detector_version) > 100:
        raise ValueError("Detector version cannot exceed 100 characters.")

    if status not in DETECTOR_STATUSES:
        raise ValueError(f"Unsupported detector status: {status}")

    if metrics is not None and not isinstance(metrics, dict):
        raise ValueError("Detector metrics must be a dictionary or None.")

    if status == "NOT_CONFIGURED" and (
        score is not None or confidence is not None
    ):
        raise ValueError(
            "A NOT_CONFIGURED detector cannot have a score or confidence."
        )

    if detector_type != "CLASSIFIER" and model_id is not None:
        raise ValueError(
            "Only CLASSIFIER results may reference a registered detector model."
        )

    score_value = _to_decimal(
        score,
        field_name="score",
        minimum=Decimal("0"),
        maximum=Decimal("100"),
        places="0.01",
    )

    confidence_value = _to_decimal(
        confidence,
        field_name="confidence",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
        places="0.001",
    )

    return (
        score_value,
        confidence_value,
        DETECTOR_SEMANTICS[detector_type],
    )


def _validate_classifier_model(
    db: Session,
    *,
    detector_type: str,
    model_id: UUID | None,
    status: str,
) -> None:

    if detector_type != "CLASSIFIER":
        return

    if status == "COMPLETED" and model_id is None:
        raise ValueError(
            "A completed classifier result must reference a registered classifier model."
        )

    if model_id is None:
        return

    model = (
        db.query(ModelRegistry)
        .filter(ModelRegistry.id == model_id)
        .first()
    )

    if model is None:
        raise ValueError(f"Model not found: {model_id}")

    if model.model_type.upper() != "CLASSIFIER":
        raise ValueError(
            f"Model '{model.model_name}' has type '{model.model_type}'. "
            "A CLASSIFIER model is required."
        )

    if not model.is_active:
        raise ValueError(
            f"Classifier model '{model.model_name}' is inactive."
        )


def create_detector_result(
    db: Session,
    *,
    run_id: UUID,
    detector_type: str,
    detector_version: str,
    status: str = "PROCESSING",
    model_id: UUID | None = None,
    score=None,
    confidence=None,
    metrics: dict | None = None,
    explanation: str | None = None,
) -> AIDetectorResult:
    """
    Create one detector result for an analysis run.

    The caller owns the transaction. This function flushes but
    never commits or rolls back.
    """

    run = (
        db.query(AIAnalysisRun)
        .filter(AIAnalysisRun.id == run_id)
        .first()
    )

    if run is None:
        raise ValueError(f"Analysis run not found: {run_id}")

    if run.status != "PROCESSING":
        raise ValueError(
            f"Cannot add detector results to run with status: {run.status}"
        )

    existing = (
        db.query(AIDetectorResult)
        .filter(
            AIDetectorResult.run_id == run_id,
            AIDetectorResult.detector_type == detector_type,
        )
        .first()
    )

    if existing is not None:
        raise ValueError(
            f"Detector {detector_type} already exists for this run. "
            "Create a new analysis run for a rerun."
        )

    score_value, confidence_value, semantics = _validate_detector_inputs(
        detector_type=detector_type,
        detector_version=detector_version,
        status=status,
        model_id=model_id,
        score=score,
        confidence=confidence,
        metrics=metrics,
    )

    _validate_classifier_model(
        db,
        detector_type=detector_type,
        model_id=model_id,
        status=status,
    )

    if explanation is not None and not isinstance(explanation, str):
        raise ValueError("Explanation must be text or None.")

    result = AIDetectorResult(
        run_id=run_id,
        detector_type=detector_type,
        detector_version=detector_version.strip(),
        model_id=model_id,
        status=status,
        score=score_value,
        score_semantics=semantics,
        confidence=confidence_value,
        metrics=metrics,
        explanation=explanation,
        completed_at=(
            datetime.now(timezone.utc)
            if status in TERMINAL_STATUSES
            else None
        ),
    )

    db.add(result)
    db.flush()

    return result


def update_detector_result(
    db: Session,
    *,
    result_id: UUID,
    status: str,
    score=None,
    confidence=None,
    metrics: dict | None = None,
    explanation: str | None = None,
) -> AIDetectorResult:
    """
    Complete or fail an existing PROCESSING detector result.
    """

    result = (
        db.query(AIDetectorResult)
        .filter(AIDetectorResult.id == result_id)
        .first()
    )

    if result is None:
        raise ValueError(f"Detector result not found: {result_id}")

    if result.status != "PROCESSING":
        raise ValueError(
            f"Cannot update detector result with status: {result.status}"
        )

    if status not in TERMINAL_STATUSES:
        raise ValueError(
            "An update must use a terminal detector status."
        )

    score_value, confidence_value, semantics = _validate_detector_inputs(
        detector_type=result.detector_type,
        detector_version=result.detector_version,
        status=status,
        model_id=result.model_id,
        score=score,
        confidence=confidence,
        metrics=metrics,
    )

    _validate_classifier_model(
        db,
        detector_type=result.detector_type,
        model_id=result.model_id,
        status=status,
    )

    if explanation is not None and not isinstance(explanation, str):
        raise ValueError("Explanation must be text or None.")

    result.status = status
    result.score = score_value
    result.score_semantics = semantics
    result.confidence = confidence_value
    result.metrics = metrics
    result.explanation = explanation
    result.completed_at = datetime.now(timezone.utc)

    db.flush()

    return result
