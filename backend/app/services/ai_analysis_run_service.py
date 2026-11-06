from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import (
    AIAnalysisRun,
    AIDetectorResult,
)
from app.models.scan import Scan
from app.models.user import User


RUN_STATUSES = {
    "PROCESSING",
    "COMPLETED",
    "PARTIAL_COMPLETED",
    "FAILED",
    "NOT_CONFIGURED",
}

TERMINAL_DETECTOR_STATUSES = {
    "COMPLETED",
    "FAILED",
    "NOT_CONFIGURED",
    "NOT_ANALYZED",
}


def create_analysis_run(
    db: Session,
    *,
    scan_id: UUID,
    initiated_by: UUID,
) -> AIAnalysisRun:
    """
    Create a new AI analysis run.

    The caller owns the transaction. This function only flushes;
    it never commits or rolls back.
    """

    scan = (
        db.query(Scan)
        .filter(Scan.id == scan_id)
        .first()
    )

    if scan is None:
        raise ValueError(
            f"Scan not found: {scan_id}"
        )

    user = (
        db.query(User)
        .filter(User.id == initiated_by)
        .first()
    )

    if user is None:
        raise ValueError(
            f"Initiating user not found: {initiated_by}"
        )

    run = AIAnalysisRun(
        scan_id=scan_id,
        initiated_by=initiated_by,
        status="PROCESSING",
    )

    db.add(run)
    db.flush()

    return run


def get_analysis_run(
    db: Session,
    *,
    run_id: UUID,
) -> AIAnalysisRun:
    """Retrieve an analysis run by its ID."""

    run = (
        db.query(AIAnalysisRun)
        .filter(AIAnalysisRun.id == run_id)
        .first()
    )

    if run is None:
        raise ValueError(
            f"AI analysis run not found: {run_id}"
        )

    return run


def finalize_analysis_run(
    db: Session,
    *,
    run_id: UUID,
) -> AIAnalysisRun:
    """
    Finalize a run using the statuses of its detector results.

    Rules:
    - All detectors completed or not analyzed -> COMPLETED
    - At least one completed and another failed/not configured -> PARTIAL_COMPLETED
    - All detectors not configured/not analyzed -> NOT_CONFIGURED
    - No detector completed and at least one failed -> FAILED

    NOT_ANALYZED is a valid terminal outcome, such as a short document
    falling below a detector's minimum text threshold.
    A run cannot be finalized while any detector is PROCESSING.
    """

    run = get_analysis_run(
        db,
        run_id=run_id,
    )

    if run.status != "PROCESSING":
        raise ValueError(
            f"Cannot finalize run with status: {run.status}"
        )

    detector_results = (
        db.query(AIDetectorResult)
        .filter(
            AIDetectorResult.run_id == run_id
        )
        .all()
    )

    if not detector_results:
        raise ValueError(
            "Cannot finalize an analysis run without detector results."
        )

    statuses = [
        result.status
        for result in detector_results
    ]

    non_terminal = [
        status
        for status in statuses
        if status not in TERMINAL_DETECTOR_STATUSES
    ]

    if non_terminal:
        raise ValueError(
            "Cannot finalize while detector results are not terminal: "
            + ", ".join(non_terminal)
        )

    completed_count = statuses.count("COMPLETED")
    blocking_statuses = {
        "FAILED",
        "NOT_CONFIGURED",
    }

    if all(
        status in {"NOT_CONFIGURED", "NOT_ANALYZED"}
        for status in statuses
    ):
        final_status = "NOT_CONFIGURED"

    elif not any(status in blocking_statuses for status in statuses):
        final_status = "COMPLETED"

    elif completed_count > 0:
        final_status = "PARTIAL_COMPLETED"

    else:
        final_status = "FAILED"

    run.status = final_status
    run.completed_at = datetime.now(timezone.utc)

    db.flush()

    return run
