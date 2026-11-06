
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

REFERENCE_TEXT = (
    "The aircraft maintained stable level flight during the "
    "evaluation. The test team recorded altitude, airspeed, "
    "engine response, and handling characteristics under "
    "specified conditions."
)

TEST_CASES = [
    {
        "name": "EXACT",
        "text": REFERENCE_TEXT,
    },
    {
        "name": "PARAPHRASED",
        "text": (
            "The aircraft sustained steady level flight "
            "throughout the assessment, while the team "
            "documented altitude, airspeed, engine response "
            "and handling behaviour under the prescribed "
            "conditions."
        ),
    },
    {
        "name": "UNRELATED",
        "text": (
            "The laboratory team measured water temperature, "
            "sample acidity, filtration efficiency and the "
            "chemical properties of collected specimens."
        ),
    },
]

db = SessionLocal()
original_source_type = settings.ai_source_type

try:
    # Find an existing user.
    user_row = db.query(User.id).first()

    if user_row is None:
        raise RuntimeError("No user exists in the database.")

    user_id = user_row[0]

    # Create a temporary scan.
    unique_value = str(uuid.uuid4())

    scan = Scan(
        title="Temporary AI Evaluation Test",
        file_name="temporary_ai_evaluation.txt",
        file_path="temporary/temporary_ai_evaluation.txt",
        file_size=sum(len(item["text"]) for item in TEST_CASES),
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

    # Create one page containing all three test sentences.
    page = ScanPage(
        scan_id=scan.id,
        page_number=1,
        raw_text="\n".join(
            item["text"] for item in TEST_CASES
        ),
    )

    db.add(page)
    db.flush()

    # Create the three scan sentences.
    for index, item in enumerate(TEST_CASES):
        sentence = ScanSentence(
            scan_id=scan.id,
            page_id=page.id,
            sentence_index=index,
            raw_text=item["text"],
            normalized_text=item["text"],
            token_count=len(item["text"].split()),
        )
        db.add(sentence)

    db.flush()

    # Add the reference passage to the AI corpus.
    content, content_created, embedding_created = (
        ingest_ai_generated_content(
            db=db,
            generated_text=REFERENCE_TEXT,
            source_model="TemporaryEvaluationModel",
            source_version="TEST-1.0",
            metadata={
                "purpose": "three_case_evaluation"
            },
        )
    )

    print("Reference corpus ID:", content.id)
    print("Content created:", content_created)
    print("Embedding created:", embedding_created)

    # Activate DATABASE source for this process only.
    settings.ai_source_type = "DATABASE"

    # Execute the actual matching service.
    print("\nRunning three-case evaluation...\n")

    matches = search_ai_copy_matches(
        db=db,
        scan_id=scan.id,
    )

    # Associate returned matches with their sentence indexes.
    matched_results = {
        match["scan_sentence"].sentence_index: match
        for match in matches
    }

    for index, test_case in enumerate(TEST_CASES):

        print("=" * 60)
        print("TEST:", test_case["name"])

        result = matched_results.get(index)

        if result is None:
            print("Result: NO QUALIFYING MATCH")
            continue

        print("Result: MATCH FOUND")
        print("Match method:", result["match_method"])
        print("Match score:", round(result["match_score"], 4))
        print("Exact score:", round(result["exact_score"], 4))
        print("N-gram score:", round(result["ngram_score"], 4))
        print("TF-IDF score:", round(result["tfidf_score"], 4))
        print("Semantic score:", round(result["semantic_score"], 4))

    print("\nTotal qualifying matches:", len(matches))

    print("\nEvaluation completed.")

except Exception:
    db.rollback()
    raise

finally:
    # Roll back all temporary scan and corpus records.
    db.rollback()

    # Restore the original source configuration.
    settings.ai_source_type = original_source_type

    db.close()

    print("\nTemporary records rolled back.")
    print("Original source configuration restored.")
