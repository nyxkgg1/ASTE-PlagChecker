from app.db.database import SessionLocal
from app.services.reference_embedding_search_service import (
    search_reference_embeddings,
)

QUERIES = [
    (
        "Engineering observations",
        "During the evaluation, the engineering team reviewed "
        "the collected observations and organized them for "
        "further assessment.",
    ),
    (
        "Environmental conditions",
        "Environmental conditions were documented to provide "
        "context for the recorded measurements.",
    ),
    (
        "Final report",
        "The final report summarizes the findings and identifies "
        "areas requiring additional investigation.",
    ),
]


def main():
    db = SessionLocal()

    try:
        for title, query in QUERIES:
            print("\n" + "=" * 80)
            print(title)
            print("Query:", query)

            results = search_reference_embeddings(
                db=db,
                query_text=query,
                limit=10,
                min_similarity=-1.0,
            )

            if not results:
                print("No reference candidates returned.")
                continue

            for rank, result in enumerate(results, start=1):
                print(
                    f"\n{rank}. Similarity: "
                    f"{result['similarity']:.4f}"
                )
                print(
                    "Reference document ID:",
                    result["reference_document_id"],
                )
                print("Reference text:", result["raw_text"])

    finally:
        db.close()


if __name__ == "__main__":
    main()
