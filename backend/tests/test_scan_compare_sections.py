import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.scan import compare_plagiarism_content
from app.models.scan import ScanSentence


class ScanCompareSectionsTests(unittest.TestCase):
    def test_comparison_matches_are_scoped_to_sentences_in_requested_scan(self):
        scan_id = uuid4()
        analysis_id = uuid4()
        scan = SimpleNamespace(
            id=scan_id,
            title="Selective scan",
            file_name="report.docx",
        )
        analysis = SimpleNamespace(id=analysis_id)

        scan_query = MagicMock()
        scan_query.filter.return_value.first.return_value = scan
        analysis_query = MagicMock()
        analysis_query.filter.return_value.order_by.return_value.first.return_value = (
            analysis
        )
        comparison_query = MagicMock()
        comparison_query.join.return_value = comparison_query
        comparison_query.options.return_value = comparison_query
        comparison_query.filter.return_value = comparison_query
        comparison_query.order_by.return_value.all.return_value = []

        db = MagicMock()
        db.query.side_effect = [
            scan_query,
            analysis_query,
            comparison_query,
        ]

        with patch(
            "app.api.routes.scan.can_access_scan",
            return_value=True,
        ):
            result = compare_plagiarism_content(
                scan_id=str(scan_id),
                db=db,
                current_user=SimpleNamespace(id=uuid4()),
            )

        self.assertEqual(result.scan_id, str(scan_id))
        self.assertEqual(result.matches, [])
        join_calls = comparison_query.join.call_args_list
        self.assertTrue(
            any(
                call.args[0] is ScanSentence
                for call in join_calls
            )
        )
        sentence_scope = ScanSentence.scan_id == scan_id
        filter_calls = comparison_query.filter.call_args_list
        self.assertTrue(
            any(
                sentence_scope.compare(call.args[0])
                if len(call.args) == 1
                else any(sentence_scope.compare(condition) for condition in call.args)
                for call in filter_calls
            )
        )


if __name__ == "__main__":
    unittest.main()
