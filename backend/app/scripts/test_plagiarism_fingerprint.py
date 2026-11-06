from app.services.plagiarism_fingerprint_service import (
    normalize_for_matching,
    tokenize,
    generate_ngram_fingerprints,
    exact_text_similarity,
    ngram_similarity,
)


def main():
    text_a = (
        "The aircraft was evaluated under standard "
        "operating conditions."
    )

    text_b = (
        "The aircraft was evaluated under standard "
        "operating conditions."
    )

    text_c = (
        "The aircraft performance was assessed "
        "during normal operating conditions."
    )

    print("NORMALIZED:")
    print(normalize_for_matching(text_a))

    print("\nTOKENS:")
    print(tokenize(text_a))

    print("\n5-GRAM FINGERPRINTS:")
    fingerprints = generate_ngram_fingerprints(
        text_a,
        n=5,
    )
    print(f"Count: {len(fingerprints)}")

    print("\nEXACT SIMILARITY:")
    print(exact_text_similarity(text_a, text_b))

    print("\nN-GRAM SIMILARITY A vs B:")
    print(ngram_similarity(text_a, text_b))

    print("\nN-GRAM SIMILARITY A vs C:")
    print(ngram_similarity(text_a, text_c))


if __name__ == "__main__":
    main()