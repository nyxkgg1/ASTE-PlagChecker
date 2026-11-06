from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.ai_detection import AIDetectionResult
from app.models.scan import ScanSentence
from app.services.ai_copy_matching_service import (
    search_ai_copy_matches,
)


ALGORITHM_VERSION = "1.0.0-AI-CORPUS"


def calculate_document_ai_score(
    sentence_results: list[dict],
) -> dict:

    if not sentence_results:
        return {
            "ai_copy_score": 0.0,
            "matched_sentences": 0,
            "total_sentences": 0,
            "sentence_coverage_percentage": 0.0,
            "matched_text_length": 0,
            "total_text_length": 0,
            "average_match_strength": 0.0,
            "maximum_match_strength": 0.0,
            "exact_match_count": 0,
            "ngram_match_count": 0,
            "semantic_match_count": 0,
        }

    total_sentences = len(
        sentence_results
    )

    meaningful_matches = [
        result
        for result in sentence_results
        if result.get("match_score", 0.0) >= 0.50
    ]

    matched_sentences = len(
        meaningful_matches
    )

    sentence_coverage = (
        matched_sentences
        / total_sentences
        * 100.0
    )

    total_text_length = sum(
        max(
            0,
            int(
                result.get(
                    "text_length",
                    0,
                )
            ),
        )
        for result in sentence_results
    )

    matched_text_length = sum(
        max(
            0,
            int(
                result.get(
                    "text_length",
                    0,
                )
            ),
        )
        for result in meaningful_matches
    )

    if total_text_length > 0:
        text_coverage = (
            matched_text_length
            / total_text_length
            * 100.0
        )
    else:
        text_coverage = 0.0

    if meaningful_matches:

        scores = [
            float(
                result.get(
                    "match_score",
                    0.0,
                )
            )
            for result in meaningful_matches
        ]

        average_match_strength = (
            sum(scores) / len(scores)
        )

        maximum_match_strength = max(scores)

    else:
        average_match_strength = 0.0
        maximum_match_strength = 0.0

    exact_match_count = sum(
        1
        for result in meaningful_matches
        if result.get("match_method")
        == "EXACT"
    )

    ngram_match_count = sum(
        1
        for result in meaningful_matches
        if result.get("match_method")
        == "NGRAM"
    )

    semantic_match_count = sum(
        1
        for result in meaningful_matches
        if result.get("match_method")
        == "SEMANTIC"
    )

    # Primary document score:
    #
    # How much of the submitted text has a meaningful
    # match against the configured AI-generated corpus.
    ai_copy_score = (
        text_coverage / 100.0
    )

    return {
        "ai_copy_score": ai_copy_score,
        "matched_sentences": matched_sentences,
        "total_sentences": total_sentences,
        "sentence_coverage_percentage": sentence_coverage,
        "matched_text_length": matched_text_length,
        "total_text_length": total_text_length,
        "text_coverage_percentage": text_coverage,
        "average_match_strength": average_match_strength,
        "maximum_match_strength": maximum_match_strength,
        "exact_match_count": exact_match_count,
        "ngram_match_count": ngram_match_count,
        "semantic_match_count": semantic_match_count,
    }


def save_ai_detection_analysis(
    db: Session,
    *,
    scan_id,
    initiated_by,
) -> AIDetectionResult:

    result = AIDetectionResult(
        scan_id=scan_id,
        initiated_by=initiated_by,
        status="PROCESSING",
        algorithm_version=ALGORITHM_VERSION,
    )

    db.add(result)
    db.flush()

    try:

        sentences = (
            db.query(ScanSentence)
            .filter(
                ScanSentence.scan_id == scan_id
            )
            .order_by(
                ScanSentence.page_id,
                ScanSentence.sentence_index,
            )
            .all()
        )

        sentence_results = []

        for sentence in sentences:

            sentence_results.append(
                {
                    "sentence_id": str(
                        sentence.id
                    ),
                    "text_length": len(
                        sentence.raw_text or ""
                    ),
                    "match_score": 0.0,
                    "match_method": None,
                }
            )

        matches = search_ai_copy_matches(
            db=db,
            scan_id=scan_id,
        )

        match_map = {}

        for match in matches:

            sentence = match[
                "scan_sentence"
            ]

            sentence_id = str(
                sentence.id
            )

            existing = match_map.get(
                sentence_id
            )

            if (
                existing is None
                or match["match_score"]
                > existing["match_score"]
            ):
                match_map[sentence_id] = match

        detailed_matches = []

        for sentence_result in sentence_results:

            sentence_id = sentence_result[
                "sentence_id"
            ]

            match = match_map.get(
                sentence_id
            )

            if not match:
                continue

            sentence_result[
                "match_score"
            ] = float(
                match["match_score"]
            )

            sentence_result[
                "match_method"
            ] = match["match_method"]

            sentence_result[
                "exact_score"
            ] = float(
                match["exact_score"]
            )

            sentence_result[
                "ngram_score"
            ] = float(
                match["ngram_score"]
            )

            sentence_result[
                "tfidf_score"
            ] = float(
                match["tfidf_score"]
            )

            sentence_result[
                "semantic_score"
            ] = float(
                match["semantic_score"]
            )

            sentence_result[
                "source_id"
            ] = match["source_id"]

            sentence_result[
                "source_text"
            ] = match["text"]

            sentence_result[
                "metadata"
            ] = match["metadata"]

            detailed_matches.append(
                sentence_result
            )

        document_score = (
            calculate_document_ai_score(
                sentence_results
            )
        )

        result.ai_probability = (
            document_score[
                "ai_copy_score"
            ]
        )

        # Confidence here means confidence in the
        # corpus-match calculation, not authorship.
        #
        # We keep this conservative until we have
        # production VayuGPT validation data.

        if (
            document_score[
                "exact_match_count"
            ] > 0
        ):
            confidence = 0.95

        elif (
            document_score[
                "ngram_match_count"
            ] > 0
            and document_score[
                "semantic_match_count"
            ] > 0
        ):
            confidence = 0.85

        elif (
            document_score[
                "semantic_match_count"
            ] > 0
        ):
            confidence = 0.70

        else:
            confidence = 0.50

        result.confidence = confidence

        result.detected_signals = {
            "detector_type": (
                "AI_GENERATED_CORPUS_MATCH"
            ),
            "algorithm_version": (
                ALGORITHM_VERSION
            ),
            "source_type": "CONFIGURED_AI_SOURCE",
            "interpretation": (
                "Measures matching against the "
                "configured AI-generated corpus. "
                "It does not independently prove "
                "AI authorship."
            ),
            "document": document_score,
            "matches": detailed_matches,
        }

        result.status = "COMPLETED"

        result.completed_at = (
            datetime.now(timezone.utc)
        )

        db.flush()

        return result

    except Exception:

        result.status = "FAILED"

        result.completed_at = (
            datetime.now(timezone.utc)
        )

        db.flush()

        raise