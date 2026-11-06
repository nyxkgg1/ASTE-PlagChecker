import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.certificate_service import create_certificate


class CertificateServiceTests(unittest.TestCase):
    def test_certificate_uses_submitted_details_and_profile_fallbacks(self):
        scan_id = uuid4()
        student_id = uuid4()
        student = SimpleNamespace(
            id=student_id,
            full_name="Profile Name",
            username="pilot",
        )
        scan = SimpleNamespace(
            id=scan_id,
            owner=student,
            scanner=student,
            title="Test report",
            file_name="report.pdf",
        )
        analysis = SimpleNamespace(overall_similarity=0.37)
        profile = SimpleNamespace(
            service_number="PROFILE-1",
            course="Profile Course",
            batch="Profile Batch",
        )

        existing_certificate_query = MagicMock()
        existing_certificate_query.filter.return_value.first.return_value = None
        analysis_query = MagicMock()
        (
            analysis_query.filter.return_value
            .order_by.return_value.first.return_value
        ) = analysis
        profile_query = MagicMock()
        profile_query.filter.return_value.first.return_value = profile

        db = MagicMock()
        db.query.side_effect = [
            existing_certificate_query,
            analysis_query,
            profile_query,
        ]

        with (
            patch(
                "app.services.certificate_service.get_certificate_directory",
                return_value=Path("/tmp"),
            ),
            patch(
                "app.services.certificate_service.generate_certificate_pdf",
            ) as generate_pdf,
            patch(
                "app.services.certificate_service.calculate_file_hash",
                return_value="certificate-hash",
            ),
        ):
            certificate = create_certificate(
                db=db,
                scan=scan,
                generated_by=SimpleNamespace(id=uuid4()),
                student_name_override="Entered Name",
                service_number_override="ENTERED-2",
                course_override="Entered Course",
                batch_override=" ",
            )

        pdf_details = generate_pdf.call_args.kwargs
        self.assertEqual(pdf_details["student_name"], "Entered Name")
        self.assertEqual(pdf_details["service_number"], "ENTERED-2")
        self.assertEqual(pdf_details["course"], "Entered Course")
        self.assertEqual(pdf_details["batch"], "Profile Batch")
        self.assertEqual(certificate.scan_id, scan_id)
        db.add.assert_called_once_with(certificate)
        db.flush.assert_called_once()


if __name__ == "__main__":
    unittest.main()
