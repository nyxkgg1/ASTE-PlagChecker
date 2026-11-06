from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.services.ai_detector_result_service import (
    classifier_model_confidence,
    latest_classifier_results_by_scan,
)


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *_):
        return self

    def filter(self, *_):
        return self

    def order_by(self, *_):
        return self

    def all(self):
        return self.rows


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.queried = False

    def query(self, *_):
        self.queried = True
        return _Query(self.rows)


class AIDetectorResultServiceTests(unittest.TestCase):
    def test_confidence_returns_saved_value(self):
        result = SimpleNamespace(confidence=0.93, score=93.0)

        self.assertEqual(classifier_model_confidence(result), 0.93)

    def test_confidence_is_derived_for_older_classifier_results(self):
        self.assertAlmostEqual(
            classifier_model_confidence(
                SimpleNamespace(confidence=None, score=93.0)
            ),
            0.93,
        )
        self.assertAlmostEqual(
            classifier_model_confidence(
                SimpleNamespace(confidence=None, score=18.0)
            ),
            0.82,
        )

    def test_latest_classifier_result_is_selected_per_scan(self):
        first_scan, second_scan = uuid4(), uuid4()
        newest = SimpleNamespace(id="newest")
        previous = SimpleNamespace(id="previous")
        other = SimpleNamespace(id="other")
        db = _Session(
            [
                (first_scan, newest),
                (first_scan, previous),
                (second_scan, other),
            ]
        )

        results = latest_classifier_results_by_scan(
            db,
            [first_scan, second_scan],
        )

        self.assertEqual(results, {first_scan: newest, second_scan: other})

    def test_empty_scan_list_does_not_query_database(self):
        db = _Session([])

        self.assertEqual(latest_classifier_results_by_scan(db, []), {})
        self.assertFalse(db.queried)


if __name__ == "__main__":
    unittest.main()
