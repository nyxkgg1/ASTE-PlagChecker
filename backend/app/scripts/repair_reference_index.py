from pathlib import Path
from datetime import datetime, timezone
import traceback

from app.db.database import SessionLocal
from app.core.config import settings
from app.models.reference import (
    ReferenceDocument,
    ReferenceDocumentVersion,
    ReferenceSentence,
)
from app.services.reference_index_service import (
    index_reference_document,
)

TARGET_IDS = [
    "af7816b7-eb72-4554-a602-fa0350ef993b",
    "31189ff0-c5ae-4e63-960e-c7e1927e3c4e",
    "76f08165-a84a-4ee5-9c22-b832d8f37285",
    "84f4013f-dca1-404a-a5a0-15443db7fce1",
    "a47b2628-d003-46d7-8c92-b15acdab2f71",
]


def resolve_file_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()

    if path.is_absolute():
        return path.resolve()

    # Existing database paths such as ../uploads/... are relative
    # to the backend working directory.
    return (Path.cwd() / path).resolve()


def main():
    db = SessionLocal()

    try:
        for reference_id in TARGET_IDS:
            print(f"\n--- Processing {reference_id} ---")

            try:
                reference = (
                    db.query(ReferenceDocument)
                    .filter(
                        ReferenceDocument.id == reference_id,
                        ReferenceDocument.status == "ACTIVE",
                    )
                    .with_for_update()
                    .first()
                )

                if reference is None:
                    print("SKIPPED: active reference not found.")
                    db.rollback()
                    continue

                existing_version = (
                    db.query(ReferenceDocumentVersion)
                    .filter(
                        ReferenceDocumentVersion.reference_document_id
                        == reference.id,
                        ReferenceDocumentVersion.version_number
                        == reference.current_version,
                    )
                    .first()
                )

                version_path = (
                    existing_version.file_path
                    if existing_version
                    else reference.file_path
                )
                resolved_path = resolve_file_path(version_path)

                if not resolved_path.is_file():
                    print(f"FAILED: file not found: {resolved_path}")
                    db.rollback()
                    continue

                if existing_version is None:
                    print("Creating missing version record.")

                    version = ReferenceDocumentVersion(
                        reference_document_id=reference.id,
                        version_number=reference.current_version,
                        file_name=reference.file_name,
                        file_path=str(resolved_path),
                        sha256_hash=reference.sha256_hash,
                        uploaded_by=reference.added_by,
                        approved_by=reference.approved_by,
                        approved_at=(
                            reference.approved_at
                            or datetime.now(timezone.utc)
                        ),
                        change_reason=(
                            "Repair missing version record for "
                            "existing reference"
                        ),
                    )
                    db.add(version)
                    db.flush()
                else:
                    print("Current version already exists.")

                sentence_count_before = (
                    db.query(ReferenceSentence)
                    .filter(
                        ReferenceSentence.reference_document_id
                        == reference.id
                    )
                    .count()
                )

                if sentence_count_before > 0:
                    print(
                        "SKIPPED indexing: already has "
                        f"{sentence_count_before} sentences."
                    )
                    db.commit()
                    continue

                # Keep the model's file path aligned with the verified
                # path used by its current version.
                reference.file_path = str(resolved_path)

                sentence_count = index_reference_document(
                    db=db,
                    reference_document=reference,
                )

                print(
                    f"SUCCESS: indexed {sentence_count} sentences "
                    f"for '{reference.title}'."
                )

            except Exception as exc:
                db.rollback()
                print(f"FAILED: {exc}")
                traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
