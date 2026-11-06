from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.scan import Scan, ScanPage, ScanSentence
from app.services.document_extraction_service import extract_document
from app.services.text_normalization_service import normalize_text
from app.services.sentence_service import split_sentences, count_tokens
from app.services.plagiarism_persistence_service import (
    save_plagiarism_analysis,
)


def calculate_sha256(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of the uploaded document.
    """

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


def has_meaningful_text(text: str) -> bool:
    """
    Determine whether extracted page text contains
    meaningful document content.

    Pages containing only:
        - whitespace
        - page numbers
        - punctuation
        - numeric values

    will not generate ScanSentence records.

    The original extracted content is still preserved
    in ScanPage.raw_text.
    """

    if not text or not text.strip():
        return False

    # Remove common punctuation and whitespace.
    cleaned = re.sub(
        r"[\W_]+",
        " ",
        text,
        flags=re.UNICODE,
    )

    cleaned = cleaned.strip()

    if not cleaned:
        return False

    # A page containing only numbers should not be
    # considered meaningful NLP content.
    if not any(character.isalpha() for character in cleaned):
        return False

    return True


def detect_mime_type(file_path: Path) -> str:
    """
    Detect MIME type from file extension.

    This is intentionally deterministic for the
    offline/on-premise environment.
    """

    extension = file_path.suffix.lower()

    mime_types = {
        ".pdf": "application/pdf",
        ".docx": (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        ".txt": "text/plain",
    }

    return mime_types.get(
        extension,
        "application/octet-stream",
    )


def create_scan_from_document(
    db: Session,
    *,
    file_path: str | Path,
    title: str,
    scanned_by,
    owner_id=None,
) -> Scan:
    """
    Complete document-processing pipeline:

        Document
            ↓
        PDF/DOCX/TXT extraction
            ↓
        Scan
            ↓
        ScanPage
            ↓
        sentence splitting
            ↓
        normalization
            ↓
        ScanSentence
            ↓
        plagiarism analysis
            ↓
        persistence

    Important design decisions:

    1. Every extracted document page becomes a ScanPage.
    2. Blank/page-number-only pages remain ScanPage records.
    3. Blank/page-number-only pages produce zero ScanSentence records.
    4. ScanSentence.raw_text preserves the sentence text extracted
       from the document.
    5. ScanSentence.normalized_text is used for matching.
    """

    path = Path(file_path)

    # ---------------------------------------------------------
    # Validate document
    # ---------------------------------------------------------

    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Document path is not a file: {path}"
        )

    # ---------------------------------------------------------
    # File metadata
    # ---------------------------------------------------------

    file_size = path.stat().st_size

    sha256_hash = calculate_sha256(path)

    mime_type = detect_mime_type(path)

    # ---------------------------------------------------------
    # Create Scan
    # ---------------------------------------------------------

    scan = Scan(
        title=title,
        file_name=path.name,
        file_path=str(path),
        file_size=file_size,
        mime_type=mime_type,
        sha256_hash=sha256_hash,
        scanned_by=scanned_by,
        owner_id=owner_id,
        status="PROCESSING",
        processing_started_at=datetime.now(timezone.utc),
    )

    db.add(scan)
    db.flush()

    try:

        # -----------------------------------------------------
        # Extract document
        # -----------------------------------------------------

        extracted_pages = extract_document(path)

        # -----------------------------------------------------
        # Process every page independently
        # -----------------------------------------------------

        for extracted_page in extracted_pages:

            original_page_text = (
                extracted_page.raw_text or ""
            )

            # -------------------------------------------------
            # Always preserve the extracted page
            # -------------------------------------------------

            page = ScanPage(
                scan_id=scan.id,
                page_number=extracted_page.page_number,
                raw_text=original_page_text,
            )

            db.add(page)
            db.flush()

            # -------------------------------------------------
            # Normalize page only for NLP processing
            # -------------------------------------------------

            normalized_page_text = normalize_text(
                original_page_text
            )

            # -------------------------------------------------
            # Ignore blank/page-number-only pages
            #
            # The ScanPage remains in the database.
            # No ScanSentence records are created.
            # -------------------------------------------------

            if not has_meaningful_text(
                normalized_page_text
            ):
                continue

            # -------------------------------------------------
            # Split this page into sentences
            #
            # We intentionally process each page independently
            # so every sentence retains its correct page.
            # -------------------------------------------------

            sentences = split_sentences(original_page_text)

            # -------------------------------------------------
            # Create ScanSentence records
            # -------------------------------------------------

            for sentence_index, normalized_sentence in enumerate(
                sentences
            ):

                normalized_sentence = (
                    normalized_sentence.strip()
                )

                if not normalized_sentence:
                    continue

                # -------------------------------------------------
                # Preserve sentence text separately from its
                # normalized matching representation.
                #
                # Preserve the source sentence for review and keep a
                # normalized copy for deterministic matching.
                # -------------------------------------------------

                sentence_raw_text = normalized_sentence

                sentence_normalized_text = normalize_text(
                    normalized_sentence
                )

                if not sentence_normalized_text:
                    continue

                sentence = ScanSentence(
                    scan_id=scan.id,
                    page_id=page.id,
                    section_id=None,
                    sentence_index=sentence_index,
                    raw_text=sentence_raw_text,
                    normalized_text=sentence_normalized_text,
                    token_count=count_tokens(
                        sentence_normalized_text
                    ),
                )

                db.add(sentence)

        # -----------------------------------------------------
        # Flush ScanPage / ScanSentence records
        # -----------------------------------------------------

        db.flush()

        # -----------------------------------------------------
        # Run plagiarism analysis
        # -----------------------------------------------------

        save_plagiarism_analysis(
            db=db,
            scan_id=scan.id,
            initiated_by=scanned_by,
        )

        # -----------------------------------------------------
        # Mark scan as completed
        # -----------------------------------------------------

        scan.status = "COMPLETED"

        scan.processing_completed_at = (
            datetime.now(timezone.utc)
        )

        db.flush()

        # -----------------------------------------------------
        # Commit complete document transaction
        # -----------------------------------------------------

        db.commit()

        db.refresh(scan)

        return scan

    except Exception:

        # -----------------------------------------------------
        # Roll back the entire document-processing transaction.
        #
        # This prevents partially processed scans from remaining
        # in the database.
        # -----------------------------------------------------

        db.rollback()

        raise