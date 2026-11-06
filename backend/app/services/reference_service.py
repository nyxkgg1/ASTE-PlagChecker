import hashlib
from pathlib import Path

from fastapi import UploadFile


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}


def calculate_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            sha256.update(chunk)

    return sha256.hexdigest()


def validate_file_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Allowed: PDF, DOCX, TXT."
        )

    return extension


async def save_reference_file(
    upload_file: UploadFile,
    destination: Path,
) -> tuple[int, str]:

    if not upload_file.filename:
        raise ValueError("Filename is required.")

    validate_file_extension(upload_file.filename)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_size = 0

    with destination.open("wb") as output:
        while True:
            chunk = await upload_file.read(1024 * 1024)

            if not chunk:
                break

            output.write(chunk)
            file_size += len(chunk)

    sha256_hash = calculate_sha256(destination)

    return file_size, sha256_hash