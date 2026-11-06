from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.db.database import SessionLocal
from app.models.reference import (
    ReferenceDocument,
    ReferenceDocumentVersion,
)
from app.services.reference_service import calculate_sha256
from app.services.reference_index_service import index_reference_document


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

FILE_PATH = (
    PROJECT_ROOT
    / "uploads"
    / "reference_documents"
    / "test_reference.txt"
)

ADMIN_USER_ID = "a038b001-4410-4506-a9c3-2238ef394bce"

FILE_NAME = "test_reference.txt"

TITLE = "Test FTER Reference Document"

DOCUMENT_TYPE = "FTER"


# ============================================================
# TEST DOCUMENT CONTENT
# ============================================================

TEST_DOCUMENT_CONTENT = """The aircraft was evaluated under standard atmospheric conditions.

The flight test team conducted the trial according to the approved test methodology.

Aircraft performance was recorded using calibrated instrumentation and data gathering equipment.

The results were analysed against the applicable flight test requirements.

The aircraft demonstrated satisfactory performance during the conducted trials.

Recommendations were prepared based on the analysis of the recorded test data.
"""


# ============================================================
# CREATE TEST FILE
# ============================================================

def create_test_file() -> None:

    FILE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    FILE_PATH.write_text(
        TEST_DOCUMENT_CONTENT,
        encoding="utf-8",
    )

    print()
    print("Test reference file created.")
    print("Path:", FILE_PATH)


# ============================================================
# VERIFY ADMIN USER
# ============================================================

def verify_admin_user(db) -> None:

    result = db.execute(
        text(
            """
            SELECT id, username, status
            FROM users
            WHERE id = :user_id
            """
        ),
        {
            "user_id": ADMIN_USER_ID,
        },
    ).fetchone()

    if not result:
        raise RuntimeError(
            "Configured admin user does not exist."
        )

    if result.status != "ACTIVE":
        raise RuntimeError(
            f"Configured admin user is not ACTIVE. "
            f"Status: {result.status}"
        )

    print()
    print("Admin user verified.")
    print("Username:", result.username)
    print("User ID:", result.id)
    print("Status:", result.status)


# ============================================================
# CREATE REFERENCE DOCUMENT
# ============================================================

def create_reference_document(db) -> ReferenceDocument:

    existing = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.file_name == FILE_NAME
        )
        .first()
    )

    if existing:

        print()
        print("Test reference document already exists.")
        print("Document ID:", existing.id)
        print(
            "Current version:",
            existing.current_version,
        )

        return existing

    file_size = FILE_PATH.stat().st_size

    sha256_hash = calculate_sha256(
        FILE_PATH
    )

    # The test document is being inserted directly by
    # the Admin and is therefore immediately approved.
    approval_time = datetime.now(timezone.utc)

    document = ReferenceDocument(
        title=TITLE,
        document_type=DOCUMENT_TYPE,
        file_name=FILE_NAME,
        file_path=str(FILE_PATH),
        file_size=file_size,
        mime_type="text/plain",
        sha256_hash=sha256_hash,
        status="ACTIVE",
        current_version=1,

        # Required by database
        added_by=ADMIN_USER_ID,
        approved_by=ADMIN_USER_ID,
        approved_at=approval_time,
    )

    db.add(document)

    db.flush()

    print()
    print("Reference document created.")
    print("Document ID:", document.id)
    print("Added by:", document.added_by)
    print("Approved by:", document.approved_by)
    print("Approved at:", document.approved_at)

    # --------------------------------------------------------
    # Create version 1
    # --------------------------------------------------------

    version = ReferenceDocumentVersion(
        reference_document_id=document.id,
        version_number=1,
        file_name=FILE_NAME,
        file_path=str(FILE_PATH),
        sha256_hash=sha256_hash,

        uploaded_by=ADMIN_USER_ID,
        approved_by=ADMIN_USER_ID,
        approved_at=approval_time,

        change_reason="Initial test reference document.",
    )

    db.add(version)

    db.commit()

    print()
    print("Reference document version created.")
    print("Version:", version.version_number)
    print("Uploaded by:", version.uploaded_by)
    print("Approved by:", version.approved_by)
    print("Approved at:", version.approved_at)

    return document


# ============================================================
# INDEX REFERENCE DOCUMENT
# ============================================================

def index_reference_document_data(
    db,
    document: ReferenceDocument,
) -> None:

    print()
    print("=" * 60)
    print("STARTING REFERENCE INDEXING")
    print("=" * 60)

    sentence_count = index_reference_document(
        db,
        document,
    )

    print()
    print("Reference indexing completed.")
    print("Sentences indexed:", sentence_count)


# ============================================================
# DATABASE VERIFICATION
# ============================================================

def verify_database() -> None:

    db = SessionLocal()

    try:

        print()
        print("=" * 60)
        print("DATABASE VERIFICATION")
        print("=" * 60)

        # ----------------------------------------------------
        # pgvector
        # ----------------------------------------------------

        pgvector = db.execute(
            text(
                """
                SELECT extname, extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            )
        ).fetchall()

        print()
        print("pgvector:", pgvector)

        # ----------------------------------------------------
        # Reference documents
        # ----------------------------------------------------

        documents = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM reference_documents
                """
            )
        ).scalar()

        print(
            "Reference documents:",
            documents,
        )

        # ----------------------------------------------------
        # Reference versions
        # ----------------------------------------------------

        versions = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM reference_document_versions
                """
            )
        ).scalar()

        print(
            "Reference versions:",
            versions,
        )

        # ----------------------------------------------------
        # Reference sentences
        # ----------------------------------------------------

        sentences = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM reference_sentences
                """
            )
        ).scalar()

        print(
            "Reference sentences:",
            sentences,
        )

        # ----------------------------------------------------
        # Fingerprints
        # ----------------------------------------------------

        fingerprints = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM reference_sentence_fingerprints
                """
            )
        ).scalar()

        print(
            "Reference fingerprints:",
            fingerprints,
        )

        # ----------------------------------------------------
        # Embeddings
        # ----------------------------------------------------

        embeddings = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM reference_embeddings
                """
            )
        ).scalar()

        print(
            "Reference embeddings:",
            embeddings,
        )

        # ----------------------------------------------------
        # 1024-dimensional vectors
        # ----------------------------------------------------

        dimensions = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM reference_embeddings
                WHERE vector_dims(embedding) = 1024
                """
            )
        ).scalar()

        print(
            "1024-dimensional embeddings:",
            dimensions,
        )

        # ----------------------------------------------------
        # Embedding model
        # ----------------------------------------------------

        model_rows = db.execute(
            text(
                """
                SELECT
                    re.model_id,
                    mr.model_name,
                    mr.version,
                    COUNT(*) AS embedding_count
                FROM reference_embeddings re
                JOIN model_registry mr
                    ON mr.id = re.model_id
                GROUP BY
                    re.model_id,
                    mr.model_name,
                    mr.version
                ORDER BY
                    mr.model_name
                """
            )
        ).fetchall()

        print()
        print("Embedding models:")

        for row in model_rows:

            print(
                "  Model ID:",
                row.model_id,
            )

            print(
                "  Model:",
                row.model_name,
            )

            print(
                "  Version:",
                row.version,
            )

            print(
                "  Embeddings:",
                row.embedding_count,
            )

        # ----------------------------------------------------
        # Reference sentences
        # ----------------------------------------------------

        sentence_rows = db.execute(
            text(
                """
                SELECT
                    page_number,
                    sentence_index,
                    normalized_text
                FROM reference_sentences
                ORDER BY
                    page_number,
                    sentence_index
                """
            )
        ).fetchall()

        print()
        print("Reference sentences:")

        for row in sentence_rows:

            print(
                f"  Page {row.page_number}, "
                f"Sentence {row.sentence_index}: "
                f"{row.normalized_text}"
            )

        # ----------------------------------------------------
        # Final status
        # ----------------------------------------------------

        print()
        print("=" * 60)

        if (
            pgvector
            and documents >= 1
            and versions >= 1
            and sentences >= 1
            and embeddings >= 1
            and dimensions == embeddings
        ):

            print(
                "END-TO-END REFERENCE INDEXING: PASSED"
            )

        else:

            print(
                "END-TO-END REFERENCE INDEXING: FAILED"
            )

        print("=" * 60)

    finally:

        db.close()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("FTER REFERENCE DOCUMENT END-TO-END TEST")
    print("=" * 60)

    db = SessionLocal()

    try:

        # 1. Create test document
        create_test_file()

        # 2. Verify Admin
        verify_admin_user(db)

        # 3. File information
        file_size = FILE_PATH.stat().st_size

        sha256_hash = calculate_sha256(
            FILE_PATH
        )

        print()
        print("File information:")
        print("  Filename:", FILE_NAME)
        print("  Size:", file_size)
        print("  SHA256:", sha256_hash)

        # 4. Create reference document
        document = create_reference_document(
            db
        )

        # 5. Index reference document
        index_reference_document_data(
            db,
            document,
        )

    except Exception:

        db.rollback()

        print()
        print("=" * 60)
        print("REFERENCE INDEXING TEST FAILED")
        print("=" * 60)

        raise

    finally:

        db.close()

    # 6. Verify everything
    verify_database()

    print()
    print("=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()