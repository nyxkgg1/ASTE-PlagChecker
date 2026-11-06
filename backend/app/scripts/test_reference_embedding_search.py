from app.db.database import SessionLocal
from app.services.reference_embedding_search_service import (
    search_reference_embeddings,
)


def run_test(
    db,
    title: str,
    query: str,
) -> None:

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    print()
    print("Query:")
    print(query)

    results = search_reference_embeddings(
        db=db,
        query_text=query,
        limit=5,
    )

    print()
    print("Results:")

    if not results:
        print("No results found.")
        return

    for index, result in enumerate(
        results,
        start=1,
    ):

        print()
        print(f"Result #{index}")
        print(
            "Similarity:",
            round(
                result["similarity"],
                4,
            ),
        )

        print(
            "Page:",
            result["page_number"],
        )

        print(
            "Sentence:",
            result["sentence_index"],
        )

        print(
            "Text:",
            result["raw_text"],
        )


def main():

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # Test 1 — Almost identical meaning
        # ----------------------------------------------------

        run_test(
            db=db,
            title="TEST 1 — SEMANTICALLY SIMILAR",
            query=(
                "The aircraft evaluation was conducted "
                "under normal atmospheric conditions."
            ),
        )

        # ----------------------------------------------------
        # Test 2 — Exact reference sentence
        # ----------------------------------------------------

        run_test(
            db=db,
            title="TEST 2 — EXACT MATCH",
            query=(
                "The aircraft was evaluated under "
                "standard atmospheric conditions."
            ),
        )

        # ----------------------------------------------------
        # Test 3 — Different meaning
        # ----------------------------------------------------

        run_test(
            db=db,
            title="TEST 3 — UNRELATED CONTENT",
            query=(
                "The maintenance team repaired the "
                "landing gear after replacing a damaged wheel."
            ),
        )

    finally:

        db.close()


if __name__ == "__main__":
    main()