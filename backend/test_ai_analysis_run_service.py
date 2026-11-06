from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.models.ai_analysis import AIAnalysisRun
from app.services.ai_analysis_run_service import finalize_analysis_run


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *_):
        return self

    def first(self):
        return self.value

    def all(self):
        return self.value


class _Session:
    def __init__(self, detector_statuses: list[str]):
        self.run = SimpleNamespace(status="PROCESSING")
        self.detectors = [
            SimpleNamespace(status=status)
            for status in detector_statuses
        ]

    def query(self, model):
        if model is AIAnalysisRun:
            return _Query(self.run)
        return _Query(self.detectors)

    def flush(self):
        pass


class FinalizeAnalysisRunTests(unittest.TestCase):
    def finalize(self, *statuses: str) -> str:
        db = _Session(list(statuses))
        result = finalize_analysis_run(db, run_id=uuid4())
        self.assertIsNotNone(result.completed_at)
        return result.status

    def test_not_analyzed_detector_does_not_make_completed_run_partial(self):
        self.assertEqual(
            self.finalize(
                "COMPLETED",
                "COMPLETED",
                "COMPLETED",
                "NOT_ANALYZED",
            ),
            "COMPLETED",
        )

    def test_failed_detector_keeps_run_partial_when_another_detector_completed(self):
        self.assertEqual(
            self.finalize("COMPLETED", "FAILED"),
            "PARTIAL_COMPLETED",
        )

    def test_unavailable_detectors_are_not_configured(self):
        self.assertEqual(
            self.finalize("NOT_CONFIGURED", "NOT_ANALYZED"),
            "NOT_CONFIGURED",
        )

    def test_run_with_no_success_and_a_failure_is_failed(self):
        self.assertEqual(
            self.finalize("FAILED", "NOT_ANALYZED"),
            "FAILED",
        )


if __name__ == "__main__":
    unittest.main()
