from app.db.database import SessionLocal
from app.models.reference import ReferenceSentence

from app.services.reference_embedding_search_service import (
    search_reference_embeddings,
)
from app.services.plagiarism_fingerprint_service import (
    exact_text_similarity,
    ngram_similarity,
)
from app.services.tfidf_similarity_service import (
    calculate_tfidf_similarity,
)
from app.services.plagiarism_search_service import (
    has_significant_evidence,
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
        for title, query_text in QUERIES:
            print("\n" + "=" * 90)
            print(title)

            candidates = search_reference_embeddings(
                db=db,
                query_text=query_text,
                limit=5,
                min_similarity=-1.0,
            )

            if not candidates:
                print("No semantic candidates returned.")
                continue

            for rank, candidate in enumerate(candidates, start=1):
                reference = (
                    db.query(ReferenceSentence)
                    .filter(
                        ReferenceSentence.id
                        == candidate["sentence_id"]
                    )
                    .first()
                )

                if reference is None:
                    print(f"\nCandidate {rank}: reference not found")
                    continue

                exact = float(
                    exact_text_similarity(
                        query_text,
                        reference.normalized_text,
                    )
                )
                ngram = float(
                    ngram_similarity(
                        query_text,
                        reference.normalized_text,
                        n=5,
                    )
                )
                tfidf = float(
                    calculate_tfidf_similarity(
                        query_text,
                        reference.normalized_text,
                    )
                )
                semantic = float(candidate["similarity"])

                accepted = has_significant_evidence(
                    exact_score=exact,
                    ngram_score=ngram,
                    tfidf_score=tfidf,
                    semantic_score=semantic,
                )

                print(f"\nCandidate {rank}")
                print(f"Semantic: {semantic:.4f}")
                print(f"Exact:    {exact:.4f}")
                print(f"N-gram:   {ngram:.4f}")
                print(f"TF-IDF:   {tfidf:.4f}")
                print(f"Accepted by evidence filter: {accepted}")
                print(f"Reference: {reference.raw_text}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
