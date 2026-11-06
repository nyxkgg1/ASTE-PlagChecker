import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.routes.scan import get_scan_document_pages


class ScanDocumentPagesAccessTests(unittest.TestCase):
    def setUp(self):
        self.scan_id = uuid4()
        self.scan = SimpleNamespace(id=self.scan_id, file_path="/tmp/unused-scan.txt")
        self.user = SimpleNamespace(id=uuid4())
        self.db = MagicMock()
        self.scan_query = MagicMock()
        self.scan_query.filter.return_value.first.return_value = self.scan
        self.db.query.return_value = self.scan_query

    @patch("app.api.routes.scan.can_access_scan", return_value=False)
    def test_denies_instructor_without_scan_access(self, can_access_scan):
        with self.assertRaises(HTTPException) as error:
            get_scan_document_pages(
                scan_id=self.scan_id,
                db=self.db,
                current_user=self.user,
            )

        self.assertEqual(error.exception.status_code, 403)
        can_access_scan.assert_called_once_with(
            db=self.db,
            scan=self.scan,
            current_user=self.user,
        )
        self.db.query.assert_called_once()

    @patch("app.api.routes.scan.can_access_scan", return_value=True)
    def test_returns_pages_for_authorized_scan(self, can_access_scan):
        page = SimpleNamespace(page_number=1, raw_text="Authorized text")
        pages_query = MagicMock()
        pages_query.filter.return_value.order_by.return_value.all.return_value = [
            page
        ]
        self.db.query.side_effect = [self.scan_query, pages_query]

        result = get_scan_document_pages(
            scan_id=self.scan_id,
            db=self.db,
            current_user=self.user,
        )

        self.assertEqual(result["scan_id"], str(self.scan_id))
        self.assertEqual(
            result["pages"],
            [{"page_number": 1, "raw_text": "Authorized text"}],
        )
        can_access_scan.assert_called_once_with(
            db=self.db,
            scan=self.scan,
            current_user=self.user,
        )

    @patch(
        "app.api.routes.scan.process_extracted_pages",
        return_value=[
            {"page_number": 1, "raw_text": "Re-extracted text", "normalized_text": "Re-extracted text"}
        ],
    )
    @patch("app.api.routes.scan.Path.is_file", return_value=True)
    @patch("app.api.routes.scan.can_access_scan", return_value=True)
    def test_reextracts_pages_when_legacy_scan_has_no_page_rows(
        self,
        can_access_scan,
        is_file,
        process_extracted_pages,
    ):
        pages_query = MagicMock()
        pages_query.filter.return_value.order_by.return_value.all.return_value = []
        self.db.query.side_effect = [self.scan_query, pages_query]

        result = get_scan_document_pages(
            scan_id=self.scan_id,
            db=self.db,
            current_user=self.user,
        )

        self.assertEqual(
            result["pages"],
            [{"page_number": 1, "raw_text": "Re-extracted text"}],
        )
        is_file.assert_called_once()
        process_extracted_pages.assert_called_once()
        can_access_scan.assert_called_once()

    @patch("app.api.routes.scan.Path.is_file", return_value=False)
    @patch("app.api.routes.scan.can_access_scan", return_value=True)
    def test_missing_pages_and_source_file_returns_clear_not_found(
        self,
        can_access_scan,
        is_file,
    ):
        pages_query = MagicMock()
        pages_query.filter.return_value.order_by.return_value.all.return_value = []
        self.db.query.side_effect = [self.scan_query, pages_query]

        with self.assertRaises(HTTPException) as error:
            get_scan_document_pages(
                scan_id=self.scan_id,
                db=self.db,
                current_user=self.user,
            )

        self.assertEqual(error.exception.status_code, 404)
        self.assertIn("original scan file is unavailable", error.exception.detail)
        is_file.assert_called_once()
        can_access_scan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
