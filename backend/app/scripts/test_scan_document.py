from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.scan import ScanPage, ScanSentence
from app.services.scan_document_service import (
    create_scan_from_document,
)


def main() -> None:

    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "python -m app.scripts.test_scan_document "
            "/path/to/document.pdf"
        )
        return

    document_path = Path(sys.argv[1])

    if not document_path.exists():
        print(
            f"ERROR: File does not exist: {document_path}"
        )
        return

    db: Session = SessionLocal()

    try:

        # Existing test/admin user
        user_id = "a038b001-4410-4506-a9c3-2238ef394bce"

        print("=" * 70)
        print("FTER DOCUMENT PROCESSING TEST")
        print("=" * 70)

        print(f"Document : {document_path}")
        print(
            f"Size     : "
            f"{document_path.stat().st_size} bytes"
        )

        # -----------------------------------------------------
        # Create scan and process document
        # -----------------------------------------------------

        scan = create_scan_from_document(
            db=db,
            file_path=document_path,
            title=document_path.stem,
            scanned_by=user_id,
            owner_id=user_id,
        )

        print()
        print("SCAN CREATED")
        print("-" * 70)
        print(f"Scan ID  : {scan.id}")
        print(f"Title    : {scan.title}")
        print(f"Filename : {scan.file_name}")
        print(f"Status   : {scan.status}")
        print(f"SHA-256  : {scan.sha256_hash}")

        # -----------------------------------------------------
        # Load pages
        # -----------------------------------------------------

        pages = (
            db.query(ScanPage)
            .filter(
                ScanPage.scan_id == scan.id
            )
            .order_by(
                ScanPage.page_number
            )
            .all()
        )

        # -----------------------------------------------------
        # Load sentences
        # -----------------------------------------------------

        sentences = (
            db.query(ScanSentence)
            .filter(
                ScanSentence.scan_id == scan.id
            )
            .order_by(
                ScanSentence.page_id,
                ScanSentence.sentence_index,
            )
            .all()
        )

        # -----------------------------------------------------
        # Create page ID → page number lookup
        # -----------------------------------------------------

        page_number_lookup = {
            str(page.id): page.page_number
            for page in pages
        }

        # -----------------------------------------------------
        # Extraction summary
        # -----------------------------------------------------

        print()
        print("EXTRACTION SUMMARY")
        print("-" * 70)
        print(f"Pages     : {len(pages)}")
        print(f"Sentences : {len(sentences)}")

        # -----------------------------------------------------
        # Page summary
        # -----------------------------------------------------

        print()
        print("PAGE SUMMARY")
        print("-" * 70)

        for page in pages:

            page_sentence_count = sum(
                1
                for sentence in sentences
                if sentence.page_id == page.id
            )

            print(
                f"Page {page.page_number:>3}: "
                f"{len(page.raw_text):>6} characters, "
                f"{page_sentence_count:>4} sentences"
            )

        # -----------------------------------------------------
        # Sentence sample
        # -----------------------------------------------------

        print()
        print("SENTENCE SAMPLE")
        print("-" * 70)

        for sentence in sentences[:10]:

            page_number = page_number_lookup.get(
                str(sentence.page_id),
                "?",
            )

            print(
                f"[Page {page_number}] "
                f"{sentence.raw_text}"
            )

        # -----------------------------------------------------
        # Success
        # -----------------------------------------------------

        print()
        print("=" * 70)
        print("PASS: DOCUMENT PIPELINE COMPLETED")
        print("=" * 70)

    except Exception as exc:

        db.rollback()

        print()
        print("=" * 70)
        print("FAIL: DOCUMENT PIPELINE")
        print("=" * 70)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()