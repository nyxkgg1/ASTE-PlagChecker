from __future__ import annotations


# ============================================================
# Configuration
# ============================================================

# These thresholds are intentionally conservative.
#
# Semantic similarity alone does NOT establish plagiarism.
#
# It must have supporting lexical evidence.

EXACT_THRESHOLD = 1.00

STRONG_NGRAM_THRESHOLD = 0.80

HIGH_SEMANTIC_THRESHOLD = 0.85
MODERATE_SEMANTIC_THRESHOLD = 0.75

TFIDF_SUPPORT_THRESHOLD = 0.20
NGRAM_SUPPORT_THRESHOLD = 0.10

STRONG_TFIDF_THRESHOLD = 0.50
STRONG_NGRAM_SUPPORT_THRESHOLD = 0.45


# ============================================================
# Helpers
# ============================================================

def clamp_score(value: float) -> float:
    """
    Keep a score between 0 and 1.
    """

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def safe_text_length(value) -> int:
    """
    Safely convert text length to a non-negative integer.
    """

    try:
        return max(
            0,
            int(value),
        )
    except (TypeError, ValueError):
        return 0


# ============================================================
# Evidence checks
# ============================================================

def has_textual_support(
    ngram_score: float,
    tfidf_score: float,
) -> bool:
    """
    Determine whether semantic similarity has enough
    lexical support to be considered meaningful.

    Semantic similarity by itself is NOT plagiarism.
    """

    ngram_score = clamp_score(
        ngram_score
    )

    tfidf_score = clamp_score(
        tfidf_score
    )

    return (
        ngram_score
        >= NGRAM_SUPPORT_THRESHOLD
        or
        tfidf_score
        >= TFIDF_SUPPORT_THRESHOLD
    )


def has_strong_textual_support(
    ngram_score: float,
    tfidf_score: float,
) -> bool:
    """
    Determine whether the candidate has strong lexical
    evidence.
    """

    ngram_score = clamp_score(
        ngram_score
    )

    tfidf_score = clamp_score(
        tfidf_score
    )

    return (
        ngram_score
        >= STRONG_NGRAM_SUPPORT_THRESHOLD
        or
        tfidf_score
        >= STRONG_TFIDF_THRESHOLD
    )


# ============================================================
# Sentence-level combined score
# ============================================================

def calculate_combined_score(
    exact_score: float,
    ngram_score: float,
    tfidf_score: float,
    semantic_score: float,
) -> dict:
    """
    Calculate the evidence score for one scan/reference
    sentence pair.

    Important:

    Semantic similarity is NOT allowed to establish
    plagiarism by itself.

    Lexical evidence must support semantic evidence.
    """

    exact_score = clamp_score(
        exact_score
    )

    ngram_score = clamp_score(
        ngram_score
    )

    tfidf_score = clamp_score(
        tfidf_score
    )

    semantic_score = clamp_score(
        semantic_score
    )

    # ========================================================
    # 1. Exact match
    # ========================================================

    if exact_score >= EXACT_THRESHOLD:

        return {
            "combined_score": 1.0,
            "match_type": "EXACT",
            "confidence": "VERY_HIGH",
            "plagiarism_evidence": True,
        }

    # ========================================================
    # 2. Strong textual match
    # ========================================================

    if ngram_score >= STRONG_NGRAM_THRESHOLD:

        return {
            "combined_score": ngram_score,
            "match_type": "STRONG_TEXTUAL_MATCH",
            "confidence": "VERY_HIGH",
            "plagiarism_evidence": True,
        }

    # ========================================================
    # 3. High semantic similarity
    #
    # Semantic similarity must have textual support.
    # ========================================================

    textual_support = has_textual_support(
        ngram_score,
        tfidf_score,
    )

    strong_textual_support = (
        has_strong_textual_support(
            ngram_score,
            tfidf_score,
        )
    )

    if (
        semantic_score
        >= HIGH_SEMANTIC_THRESHOLD
        and textual_support
    ):

        # Weighted evidence score.
        #
        # Textual evidence receives significant weight because
        # semantic similarity alone is insufficient.

        combined_score = (
            (0.30 * ngram_score)
            + (0.25 * tfidf_score)
            + (0.45 * semantic_score)
        )

        combined_score = clamp_score(
            combined_score
        )

        return {
            "combined_score": combined_score,
            "match_type": "HIGH_SIMILARITY",
            "confidence": "HIGH",
            "plagiarism_evidence": True,
        }

    # ========================================================
    # 4. Moderate semantic similarity
    #
    # Require stronger lexical support.
    # ========================================================

    if (
        semantic_score
        >= MODERATE_SEMANTIC_THRESHOLD
        and strong_textual_support
    ):

        combined_score = (
            (0.35 * ngram_score)
            + (0.25 * tfidf_score)
            + (0.40 * semantic_score)
        )

        combined_score = clamp_score(
            combined_score
        )

        return {
            "combined_score": combined_score,
            "match_type": "MODERATE_SIMILARITY",
            "confidence": "MEDIUM",
            "plagiarism_evidence": True,
        }

    # ========================================================
    # 5. Purely lexical evidence
    #
    # This catches textual overlap even when semantic similarity
    # is not particularly high.
    # ========================================================

    if (
        ngram_score >= 0.25
        or tfidf_score >= 0.35
    ):

        combined_score = (
            (0.55 * ngram_score)
            + (0.45 * tfidf_score)
        )

        combined_score = clamp_score(
            combined_score
        )

        if (
            ngram_score >= 0.45
            and tfidf_score >= 0.50
        ):

            match_type = "STRONG_TEXTUAL_MATCH"
            confidence = "HIGH"

        else:

            match_type = "LOW_SIMILARITY"
            confidence = "LOW"

        return {
            "combined_score": combined_score,
            "match_type": match_type,
            "confidence": confidence,
            "plagiarism_evidence": True,
        }

    # ========================================================
    # 6. No significant evidence
    # ========================================================

    return {
        "combined_score": 0.0,
        "match_type": "NO_SIGNIFICANT_MATCH",
        "confidence": "LOW",
        "plagiarism_evidence": False,
    }


# ============================================================
# Document-level score
# ============================================================

def calculate_document_score(
    sentence_results: list[dict],
) -> dict:
    """
    Calculate document-level plagiarism evidence.

    The main document score is based on the proportion of
    submitted text that has meaningful plagiarism evidence.

    Match strength is also used as an evidence multiplier.

    Example:

        20% of document text matched
        with average match strength 0.90

        effective evidence ~= 18%

    This prevents a weak similarity from contributing as
    strongly as an exact copy.
    """

    # ========================================================
    # Empty document
    # ========================================================

    if not sentence_results:

        return {
            "document_score": 0.0,

            "matched_sentences": 0,
            "total_sentences": 0,
            "sentence_coverage_percentage": 0.0,

            "matched_text_length": 0,
            "total_text_length": 0,
            "text_coverage_percentage": 0.0,

            "evidence_weighted_score": 0.0,

            "average_match_strength": 0.0,
            "maximum_match_strength": 0.0,

            "exact_match_count": 0,
            "strong_textual_match_count": 0,
            "high_similarity_count": 0,
            "moderate_similarity_count": 0,
            "low_similarity_count": 0,
            "semantic_match_count": 0,
        }

    # ========================================================
    # Total sentence count
    # ========================================================

    total_sentences = len(
        sentence_results
    )

    # ========================================================
    # Total document text
    # ========================================================

    total_text_length = sum(
        safe_text_length(
            result.get(
                "text_length",
                0,
            )
        )
        for result in sentence_results
    )

    # ========================================================
    # Meaningful plagiarism matches
    # ========================================================
    meaningful_matches = [
        result
        for result in sentence_results
            if result.get("plagiarism_evidence",False,)
    ]

    matched_sentences = len(
        meaningful_matches
    )

    # ========================================================
    # Sentence coverage
    # ========================================================

    if total_sentences > 0:

        sentence_coverage_percentage = (
            matched_sentences
            / total_sentences
        ) * 100.0

    else:

        sentence_coverage_percentage = 0.0

    # ========================================================
    # Matched text length
    # ========================================================

    matched_text_length = sum(
        safe_text_length(
            result.get(
                "text_length",
                0,
            )
        )
        for result in meaningful_matches
    )

    if total_text_length > 0:

        text_coverage_percentage = (
            matched_text_length
            / total_text_length
        ) * 100.0

    else:

        text_coverage_percentage = 0.0

    # ========================================================
    # Match strength
    # ========================================================

    if meaningful_matches:

        match_scores = [
            clamp_score(
                result.get(
                    "combined_score",
                    0.0,
                )
            )
            for result in meaningful_matches
        ]

        average_match_strength = (
            sum(match_scores)
            / len(match_scores)
        )

        maximum_match_strength = max(
            match_scores
        )

    else:

        average_match_strength = 0.0
        maximum_match_strength = 0.0

    # ========================================================
    # Evidence-weighted text coverage
    #
    # Each matched sentence contributes according to:
    #
    #     text length × match strength
    #
    # This prevents a weak 0.50 similarity from being treated
    # exactly like a 1.00 exact copy.
    # ========================================================

    evidence_weighted_text = sum(
        safe_text_length(
            result.get(
                "text_length",
                0,
            )
        )
        * clamp_score(
            result.get(
                "combined_score",
                0.0,
            )
        )
        for result in meaningful_matches
    )

    if total_text_length > 0:

        evidence_weighted_score = (
            evidence_weighted_text
            / total_text_length
        )

    else:

        evidence_weighted_score = 0.0

    evidence_weighted_score = clamp_score(
        evidence_weighted_score
    )

    # ========================================================
    # Final document score
    #
    # We use evidence-weighted coverage as the primary score.
    #
    # This means:
    #
    # Exact match:
    #     100% contribution
    #
    # Strong textual match:
    #     high contribution
    #
    # Weaker similarity:
    #     proportionally lower contribution
    # ========================================================

    document_score = (
        evidence_weighted_score
    )

    # ========================================================
    # Match-type statistics
    # ========================================================

    exact_match_count = sum(
        1
        for result in meaningful_matches
        if result.get(
            "match_type"
        ) == "EXACT"
    )

    strong_textual_match_count = sum(
        1
        for result in meaningful_matches
        if result.get(
            "match_type"
        ) == "STRONG_TEXTUAL_MATCH"
    )

    high_similarity_count = sum(
        1
        for result in meaningful_matches
        if result.get(
            "match_type"
        ) == "HIGH_SIMILARITY"
    )

    moderate_similarity_count = sum(
        1
        for result in meaningful_matches
        if result.get(
            "match_type"
        ) == "MODERATE_SIMILARITY"
    )

    low_similarity_count = sum(
        1
        for result in meaningful_matches
        if result.get(
            "match_type"
        ) == "LOW_SIMILARITY"
    )

    semantic_match_count = sum(
        1
        for result in meaningful_matches
        if clamp_score(
            result.get(
                "semantic_score",
                0.0,
            )
        ) >= HIGH_SEMANTIC_THRESHOLD
    )

    # ========================================================
    # Return complete document statistics
    # ========================================================

    return {
        "document_score": document_score,

        "matched_sentences": matched_sentences,
        "total_sentences": total_sentences,

        "sentence_coverage_percentage": (
            sentence_coverage_percentage
        ),

        "matched_text_length": matched_text_length,
        "total_text_length": total_text_length,

        "text_coverage_percentage": (
            text_coverage_percentage
        ),

        "evidence_weighted_score": (
            evidence_weighted_score
        ),

        "average_match_strength": (
            average_match_strength
        ),

        "maximum_match_strength": (
            maximum_match_strength
        ),

        "exact_match_count": (
            exact_match_count
        ),

        "strong_textual_match_count": (
            strong_textual_match_count
        ),

        "high_similarity_count": (
            high_similarity_count
        ),

        "moderate_similarity_count": (
            moderate_similarity_count
        ),

        "low_similarity_count": (
            low_similarity_count
        ),

        "semantic_match_count": (
            semantic_match_count
        ),
    }
