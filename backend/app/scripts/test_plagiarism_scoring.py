from app.services.plagiarism_scoring_service import (
    calculate_combined_score,
)


def test_case(
    name: str,
    exact: float,
    ngram: float,
    tfidf: float,
    semantic: float,
) -> None:

    result = calculate_combined_score(
        exact_score=exact,
        ngram_score=ngram,
        tfidf_score=tfidf,
        semantic_score=semantic,
    )

    print()
    print("=" * 80)
    print(name)
    print("=" * 80)

    print()
    print("Exact:", exact)
    print("N-gram:", ngram)
    print("TF-IDF:", tfidf)
    print("Semantic:", semantic)

    print()
    print("Combined Score:")
    print(
        round(
            result["combined_score"],
            4,
        )
    )

    print(
        "Match Type:",
        result["match_type"],
    )

    print(
        "Confidence:",
        result["confidence"],
    )


def main():

    # --------------------------------------------------
    # Exact copy
    # --------------------------------------------------

    test_case(
        name="EXACT COPY",
        exact=1.0,
        ngram=1.0,
        tfidf=1.0,
        semantic=1.0,
    )

    # --------------------------------------------------
    # Paraphrased sentence from our real test
    # --------------------------------------------------

    test_case(
        name="PARAPHRASED",
        exact=0.0,
        ngram=0.0,
        tfidf=0.3373,
        semantic=0.9672,
    )

    # --------------------------------------------------
    # Unrelated sentence from our real test
    # --------------------------------------------------

    test_case(
        name="UNRELATED",
        exact=0.0,
        ngram=0.0,
        tfidf=0.0498,
        semantic=0.6162,
    )

    # --------------------------------------------------
    # Strong textual overlap
    # --------------------------------------------------

    test_case(
        name="STRONG TEXTUAL OVERLAP",
        exact=0.0,
        ngram=0.85,
        tfidf=0.80,
        semantic=0.90,
    )


if __name__ == "__main__":
    main()
