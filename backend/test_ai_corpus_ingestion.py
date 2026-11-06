
from app.db.database import SessionLocal
from app.services.ai_corpus_ingestion_service import (
    ingest_ai_generated_content,
)

sample_text = """
The aircraft demonstrated stable level flight characteristics
during the evaluation conducted under the specified test conditions.
The flight test team recorded aircraft response and system performance
for subsequent technical analysis.
"""

db = SessionLocal()

try:
    content, content_created, embedding_created = (
        ingest_ai_generated_content(
            db=db,
            generated_text=sample_text,
            source_model="Test AI Model",
            source_version="1.0",
            metadata={
                "document_type": "FTER",
                "test_record": True,
            },
        )
    )

    db.commit()

    print("First ingestion:")
    print("Content ID:", content.id)
    print("Content created:", content_created)
    print("Embedding created:", embedding_created)
    print("Content hash:", content.content_hash)

    content2, content_created2, embedding_created2 = (
        ingest_ai_generated_content(
            db=db,
            generated_text=sample_text,
            source_model="Test AI Model",
            source_version="1.0",
            metadata={
                "document_type": "FTER",
                "test_record": True,
            },
        )
    )

    db.commit()

    print("\nDuplicate ingestion:")
    print("Content ID:", content2.id)
    print("Content created:", content_created2)
    print("Embedding created:", embedding_created2)

except Exception:
    db.rollback()
    raise

finally:
    db.close()

