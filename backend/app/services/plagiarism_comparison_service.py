from __future__ import annotations

from app.services.plagiarism_fingerprint_service import (
    exact_text_similarity,
    ngram_similarity,
)
from app.services.tfidf_similarity_service import (
    calculate_tfidf_similarity,
)
from app.services.reference_embedding_search_service import (
    search_reference_embeddings,
)


def compare_sentences(
    scan_text: str,
    reference_text: str,
) -> dict:

    exact_score = exact_text_similarity(
        scan_text,
        reference_text,
    )

    ngram_score = ngram_similarity(
        scan_text,
        reference_text,
        n=5,
    )

    tfidf_score = calculate_tfidf_similarity(
        scan_text,
        reference_text,
    )

    # Exact match takes absolute precedence.
    if exact_score >= 1.0:

        final_score = 1.0
        method = "EXACT"

    else:

        final_score = max(
            ngram_score,
            tfidf_score,
        )

        if ngram_score >= tfidf_score:
            method = "NGRAM"
        else:
            method = "TFIDF"

    return {
        "exact_score": exact_score,
        "ngram_score": ngram_score,
        "tfidf_score": tfidf_score,
        "semantic_score": None,
        "final_score": final_score,
        "method": method,
    }
