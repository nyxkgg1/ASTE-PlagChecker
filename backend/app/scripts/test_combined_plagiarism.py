
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.reference import ReferenceSentence
from app.services.plagiarism_comparison_service import (
    compare_sentences,
)
from app.services.plagiarism_search_service import (
    find_semantic_candidates,
)


# ============================================================
# Helper
# ============================================================

class FakeScanSentence:
    """
    Lightweight test object that behaves like ScanSentence
    for the semantic-search test.
    """

    def __init__(self, text: str):
        self.raw_text = text
        self.normalized_text = text
        self.token_count = len(text.split())


# ============================================================
# Formatting helpers
# ============================================================

def print_score(
    label: str,
    value,
) -> None:

    if value is None:
        print(f"{label:<18} None")
    else:
        print(
            f"{label:<18} {float(value):.4f}"
        )


# ============================================================
# Main test
# ============================================================

def main():

    db: Session = SessionLocal()

    try:

        # ----------------------------------------------------
        # Find reference sentence
        # ----------------------------------------------------

        reference = (
            db.query(ReferenceSentence)
            .order_by(
                ReferenceSentence.sentence_index
            )
            .first()
        )

        if not reference:

            print()
            print(
                "No reference sentence found."
            )

            return

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        print()
        print("=" * 90)
        print("COMBINED PLAGIARISM ENGINE TEST")
        print("=" * 90)

        print()
        print("Reference sentence:")
        print(reference.normalized_text)

        print()
        print("Reference ID:")
        print(reference.id)

        # ----------------------------------------------------
        # Test cases
        # ----------------------------------------------------

        test_queries = [

            (
                "EXACT",
                "The aircraft was evaluated under "
                "standard atmospheric conditions.",
            ),

            (
                "PARAPHRASE",
                "The aircraft was assessed in "
                "normal atmospheric conditions.",
            ),

            (
                "UNRELATED",
                "The weather forecast indicates "
                "heavy rainfall tomorrow.",
            ),

        ]

        # ----------------------------------------------------
        # Execute test cases
        # ----------------------------------------------------

        for test_name, query in test_queries:

            print()
            print("=" * 90)
            print(test_name)
            print("=" * 90)

            print()
            print("Query:")
            print(query)

            # ------------------------------------------------
            # Lexical comparison
            # ------------------------------------------------

            lexical_result = compare_sentences(
                scan_text=query,
                reference_text=reference.normalized_text,
            )

            exact_score = float(
                lexical_result.get(
                    "exact_score",
                    0.0,
                )
            )

            ngram_score = float(
                lexical_result.get(
                    "ngram_score",
                    0.0,
                )
            )

            tfidf_score = float(
                lexical_result.get(
                    "tfidf_score",
                    0.0,
                )
            )

            print()
            print("LEXICAL SCORES")
            print("-" * 40)

            print_score(
                "Exact:",
                exact_score,
            )

            print_score(
                "N-gram:",
                ngram_score,
            )

            print_score(
                "TF-IDF:",
                tfidf_score,
            )

            print_score(
                "Lexical final:",
                lexical_result.get(
                    "final_score"
                ),
            )

            print(
                "Lexical method:  ",
                lexical_result.get(
                    "method"
                ),
            )

            # ------------------------------------------------
            # Semantic comparison
            # ------------------------------------------------
            scan_sentence = FakeScanSentence(query)
            semantic_results = find_semantic_candidates(db,scan_sentence,)
            print()
            print("SEMANTIC SEARCH")
            print("-" * 40)

            if not semantic_results:

                print(
                    "No semantic candidates found."
                )

                semantic_score = 0.0

            else:

                print(
                    "Candidates:",
                    len(semantic_results),
                )

                # Raw semantic-search results use the key
                # "similarity", not "semantic_score".
                best_semantic = max(
                    semantic_results,
                 key=lambda result: float(
                        result.get(
                            "similarity",
                            0.0,
                        )
                    ),
                )

                semantic_score = float(
                    best_semantic.get(
                        "similarity",
                        0.0,
                    )
                )

                print(
                    "Best semantic score:",
                    f"{semantic_score:.4f}",
                )

                print()
                print(
                    "Best reference sentence:"
                )

                print(
                    best_semantic.get(
                        "normalized_text",
                        "",
                    )
                )

            # ------------------------------------------------
            # Combined evidence
            # ------------------------------------------------

            print()
            print("COMBINED EVIDENCE")
            print("-" * 40)

            print_score(
                "Exact:",
                exact_score,
            )

            print_score(
                "N-gram:",
                ngram_score,
            )

            print_score(
                "TF-IDF:",
                tfidf_score,
            )

            print_score(
                "Semantic:",
                semantic_score,
            )

            # ------------------------------------------------
            # Simple diagnostic interpretation
            # ------------------------------------------------

            if exact_score >= 1.0:

                diagnostic = (
                    "EXACT TEXTUAL MATCH DETECTED"
                )

            elif (
                ngram_score >= 0.45
                or tfidf_score >= 0.50
            ):

                diagnostic = (
                    "STRONG TEXTUAL EVIDENCE"
                )

            elif semantic_score >= 0.85:

                diagnostic = (
                    "HIGH SEMANTIC SIMILARITY"
                )

            elif semantic_score >= 0.75:

                diagnostic = (
                    "MODERATE SEMANTIC SIMILARITY"
                )

            else:

                diagnostic = (
                    "NO STRONG MATCH EVIDENCE"
                )

            print()
            print(
                "Diagnostic:",
                diagnostic,
            )

        # ----------------------------------------------------
        # Completion
        # ----------------------------------------------------

        print()
        print("=" * 90)
        print(
            "COMBINED PLAGIARISM ENGINE TEST COMPLETED"
        )
        print("=" * 90)

    finally:

        db.close()


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
