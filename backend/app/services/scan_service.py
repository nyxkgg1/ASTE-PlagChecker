from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.services.document_extraction_service import extract_document
from app.services.text_normalization_service import normalize_text
from app.services.sentence_service import (
    count_tokens,
    split_sentences,
)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}


def get_scan_upload_directory() -> Path:
    """
    Return the directory used for uploaded scan documents.
    """

    upload_dir = Path(settings.upload_dir)

    if not upload_dir.is_absolute():
        upload_dir = (
            Path(__file__).resolve().parents[2]
            / upload_dir
        )

    scan_dir = upload_dir / "scans"
    scan_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return scan_dir



async def save_scan_file(
    document: UploadFile,
    destination_folder: str = "",
):
    """
    Save an uploaded scan document in a validated subfolder
    beneath the configured scans storage directory.

    Returns:
        file_path, file_size, sha256_hash, extension
    """
    original_filename = document.filename or ""
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Allowed types: PDF, DOCX and TXT."
        )

    # Resolve the existing storage directory.
    scan_directory = get_scan_upload_directory().resolve()

    # The requested destination must be a relative subfolder.
    requested_folder = Path(destination_folder.strip() or ".")

    if requested_folder.is_absolute():
        raise ValueError(
            "Destination must be a relative subfolder of the scan storage directory."
        )

    destination = (scan_directory / requested_folder).resolve()

    # Prevent directory traversal and symlink-based escape.
    if not destination.is_relative_to(scan_directory):
        raise ValueError(
            "Invalid destination folder. Choose a folder inside the scan storage directory."
        )

    destination.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4()}{extension}"
    file_path = destination / stored_filename

    sha256 = hashlib.sha256()
    file_size = 0

    try:
        with file_path.open("wb") as output_file:
            while True:
                chunk = await document.read(1024 * 1024)
                if not chunk:
                    break

                output_file.write(chunk)
                file_size += len(chunk)
                sha256.update(chunk)

    except Exception:
        if file_path.exists():
            file_path.unlink()
        raise

    return file_path, file_size, sha256.hexdigest(), extension


def process_extracted_pages(
    file_path: Path,
) -> list[dict]:
    """
    Extract and normalize document pages.

    Returns a list containing:

        {
            "page_number": int,
            "raw_text": str,
            "normalized_text": str,
        }
    """

    pages = extract_document(
        Path(file_path)
    )

    processed_pages = []

    for page in pages:

        raw_text = page.raw_text or ""

        normalized_text = normalize_text(
            raw_text
        )

        if not normalized_text:
            continue

        processed_pages.append(
            {
                "page_number": page.page_number,
                "raw_text": raw_text,
                "normalized_text": normalized_text,
                "heading_lines": page.heading_lines,
            }
        )

    return processed_pages


def process_page_sentences(
    normalized_text: str,
) -> list[dict]:
    """
    Split normalized page text into sentences.
    """

    sentences = split_sentences(
        normalized_text
    )

    processed_sentences = []

    for sentence_index, sentence in enumerate(
        sentences,
        start=1,
    ):

        raw_sentence = sentence.strip()

        if not raw_sentence:
            continue

        normalized_sentence = normalize_text(
            raw_sentence
        )

        if not normalized_sentence:
            continue

        processed_sentences.append(
            {
                "sentence_index": sentence_index,
                "raw_text": raw_sentence,
                "normalized_text": normalized_sentence,
                "token_count": count_tokens(
                    normalized_sentence
                ),
            }
        )

    return processed_sentences