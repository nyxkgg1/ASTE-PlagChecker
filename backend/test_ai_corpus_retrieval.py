
from app.db.database import SessionLocal
from app.services.ai_corpus_ingestion_service import (
    ingest_ai_generated_content,
)
from app.services.ai_source.database_source import (
    DatabaseAIContentSource,
)

TEST_DOCUMENTS = [
    {
        "text": (
            "The aircraft demonstrated stable level flight "
            "characteristics during the evaluation. The flight "
            "test team recorded altitude, airspeed, engine "
            "parameters and aircraft response under specified "
            "test conditions."
        ),
        "model": "TestModel-A",
    },
    {
        "text": (
            "During the climb performance evaluation, the aircraft "
            "maintained the required climb profile. The evaluation "
            "recorded rate of climb, engine response and altitude "
            "changes at different flight conditions."
        ),
        "model": "TestModel-B",
    },
]

db = SessionLocal()
inserted_ids = []

try:
    # Insert temporary documents and generate embeddings.
    for item in TEST_DOCUMENTS:
        content, content_created, embedding_created = (
            ingest_ai_generated_content(
                db=db,
                generated_text=item["text"],
                source_model=item["model"],
                source_version="TEST-1.0",
                metadata={"purpose": "temporary_retrieval_test"},
            )
        )

        inserted_ids.append(content.id)

        print("\nInserted document:")
        print("ID:", content.id)
        print("Content created:", content_created)
        print("Embedding created:", embedding_created)

    db.commit()

    # Instantiate the PostgreSQL retrieval source directly.
    source = DatabaseAIContentSource(db=db)

    queries = [
        "aircraft altitude airspeed engine parameters",
        "aircraft performance while gaining altitude",
    ]

    for query in queries:
        print("\n" + "=" * 65)
        print("QUERY:", query)

        results = source.search(query_text=query, limit=5)

        if not results:
            print("No results returned.")
            continue

        for index, result in enumerate(results, start=1):
            print(f"\nResult {index}")
            print("Source ID:", result.source_id)
            print("Source model:", result.metadata.get("source_model"))
            print("Text:", result.text)
            print("Retrieval:", result.metadata.get("retrieval"))

except Exception:
    db.rollback()
    raise

finally:
    # Remove only the temporary documents inserted by this test.
    if inserted_ids:
        try:
            from app.models.ai_generated_content import (
                AIGeneratedContent,
            )

            db.query(AIGeneratedContent).filter(
                AIGeneratedContent.id.in_(inserted_ids)
            ).delete(synchronize_session=False)

            db.commit()
            print("\nTemporary test documents cleaned up.")

        except Exception:
            db.rollback()
            raise

    db.close()
