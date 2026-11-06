
import hashlib
import uuid

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.user import User
from app.models.scan import Scan, ScanPage, ScanSentence
from app.services.ai_corpus_ingestion_service import (
    ingest_ai_generated_content,
)
from app.services.ai_copy_matching_service import (
    search_ai_copy_matches,
)


TEST_SENTENCE = (
    "The aircraft maintained stable level flight while the "
    "evaluation team recorded altitude, airspeed, engine response, "
    "and aircraft handling characteristics under the specified "
    "test conditions."
)


db = SessionLocal()
original_source_type = settings.ai_source_type

try:
    # --------------------------------------------------
    # 1. Find an existing user for the temporary scan.
    # --------------------------------------------------

    user_id = db.query(User.id).first()

    if user_id is None:
        raise RuntimeError(
            "No user exists in the database. "
            "Cannot create the temporary scan."
        )

    user_id = user_id[0]

    # --------------------------------------------------
    # 2. Create a temporary scan.
    # --------------------------------------------------

    unique_value = str(uuid.uuid4())

    scan = Scan(
        title="Temporary AI Matching Test",
        file_name="temporary_ai_matching_test.txt",
        file_path="temporary/temporary_ai_matching_test.txt",
        file_size=len(TEST_SENTENCE),
        mime_type="text/plain",
        sha256_hash=hashlib.sha256(
            unique_value.encode("utf-8")
        ).hexdigest(),
        scanned_by=user_id,
        owner_id=user_id,
        status="UPLOADED",
    )

    db.add(scan)
    db.flush()

    # --------------------------------------------------
    # 3. Create a temporary scan page.
    # --------------------------------------------------

    page = ScanPage(
        scan_id=scan.id,
        page_number=1,
        raw_text=TEST_SENTENCE,
    )

    db.add(page)
    db.flush()

    # --------------------------------------------------
    # 4. Create a temporary scan sentence.
    # --------------------------------------------------

    sentence = ScanSentence(
        scan_id=scan.id,
        page_id=page.id,
        sentence_index=0,
        raw_text=TEST_SENTENCE,
        normalized_text=TEST_SENTENCE,
        token_count=len(TEST_SENTENCE.split()),
    )

    db.add(sentence)
    db.flush()

    print("Temporary scan created:", scan.id)
    print("Temporary sentence created:", sentence.id)

    # --------------------------------------------------
    # 5. Insert the same passage into the AI corpus.
    # --------------------------------------------------

    content, content_created, embedding_created = (
        ingest_ai_generated_content(
            db=db,
            generated_text=TEST_SENTENCE,
            source_model="TemporaryTestModel",
            source_version="TEST-1.0",
            metadata={
                "purpose": "complete_matching_test"
            },
        )
    )

    print("\nCorpus document:", content.id)
    print("Content created:", content_created)
    print("Embedding created:", embedding_created)

    # --------------------------------------------------
    # 6. Temporarily activate DATABASE source.
    # --------------------------------------------------

    settings.ai_source_type = "DATABASE"

    # --------------------------------------------------
    # 7. Execute the actual matching service.
    # --------------------------------------------------

    print("\nRunning search_ai_copy_matches()...")

    matches = search_ai_copy_matches(
        db=db,
        scan_id=scan.id,
    )

    print("\nTotal matches:", len(matches))

    for index, match in enumerate(matches, start=1):
        print(f"\nMatch {index}")
        print("Source ID:", match["source_id"])
        print("Match method:", match["match_method"])
        print("Match score:", match["match_score"])
        print("Exact score:", match["exact_score"])
        print("N-gram score:", match["ngram_score"])
        print("TF-IDF score:", match["tfidf_score"])
        print("Semantic score:", match["semantic_score"])

    if not matches:
        raise AssertionError(
            "No matches returned by the matching service."
        )

    if matches[0]["match_method"] != "EXACT":
        raise AssertionError(
            "Expected EXACT match but received "
            + str(matches[0]["match_method"])
        )

    if matches[0]["match_score"] != 1.0:
        raise AssertionError(
            "Expected exact match score of 1.0."
        )

    print("\nSUCCESS: Complete matching workflow passed.")

except Exception:
    db.rollback()
    raise

finally:
    # Remove every temporary database change.
    db.rollback()

    # Restore original source configuration.
    settings.ai_source_type = original_source_type

    db.close()

    print("\nTemporary database changes rolled back.")
    print("Original AI source configuration restored.")
