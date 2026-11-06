from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.ai_detection import AIDetectionResult
from app.models.scan import ScanSentence


ALGORITHM_VERSION = "0.1.0-HEURISTIC"


# ---------------------------------------------------------------------------
# Basic text utilities
# ---------------------------------------------------------------------------

def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def tokenize_words(text: str) -> list[str]:
    if not text:
        return []

    return re.findall(
        r"\b[A-Za-z][A-Za-z'-]*\b",
        text.lower(),
    )


def split_sentences(text: str) -> list[str]:
    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text.strip(),
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


# ---------------------------------------------------------------------------
# Signal calculations
# ---------------------------------------------------------------------------

def calculate_average_sentence_length(
    sentences: list[str],
) -> float:
    if not sentences:
        return 0.0

    lengths = [
        len(tokenize_words(sentence))
        for sentence in sentences
    ]

    return sum(lengths) / len(lengths)


def calculate_sentence_length_variance(
    sentences: list[str],
) -> float:
    if len(sentences) < 2:
        return 0.0

    lengths = [
        len(tokenize_words(sentence))
        for sentence in sentences
    ]

    mean = sum(lengths) / len(lengths)

    variance = sum(
        (length - mean) ** 2
        for length in lengths
    ) / len(lengths)

    return variance


def calculate_sentence_length_cv(
    sentences: list[str],
) -> float:
    if len(sentences) < 2:
        return 0.0

    lengths = [
        len(tokenize_words(sentence))
        for sentence in sentences
    ]

    mean = sum(lengths) / len(lengths)

    if mean == 0:
        return 0.0

    variance = sum(
        (length - mean) ** 2
        for length in lengths
    ) / len(lengths)

    standard_deviation = math.sqrt(variance)

    return standard_deviation / mean


def calculate_lexical_diversity(
    words: list[str],
) -> float:
    if not words:
        return 0.0

    unique_words = set(words)

    return len(unique_words) / len(words)


def calculate_repetition_ratio(
    words: list[str],
) -> float:
    if not words:
        return 0.0

    counts = Counter(words)

    repeated_tokens = sum(
        count - 1
        for count in counts.values()
        if count > 1
    )

    return repeated_tokens / len(words)


def calculate_punctuation_density(
    text: str,
) -> float:
    if not text:
        return 0.0

    characters = len(text)

    if characters == 0:
        return 0.0

    punctuation_count = len(
        re.findall(
            r"[,:;.!?]",
            text,
        )
    )

    return punctuation_count / characters


def calculate_digit_ratio(
    text: str,
) -> float:
    if not text:
        return 0.0

    characters = len(text)

    if characters == 0:
        return 0.0

    digit_count = sum(
        character.isdigit()
        for character in text
    )

    return digit_count / characters


def calculate_word_length_variation(
    words: list[str],
) -> float:
    if len(words) < 2:
        return 0.0

    lengths = [
        len(word)
        for word in words
    ]

    mean = sum(lengths) / len(lengths)

    if mean == 0:
        return 0.0

    variance = sum(
        (length - mean) ** 2
        for length in lengths
    ) / len(lengths)

    return math.sqrt(variance) / mean


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def extract_ai_signals(
    text: str,
) -> dict:
    if not text or not text.strip():
        return {
            "word_count": 0,
            "sentence_count": 0,
            "average_sentence_length": 0.0,
            "sentence_length_variance": 0.0,
            "sentence_length_cv": 0.0,
            "lexical_diversity": 0.0,
            "repetition_ratio": 0.0,
            "punctuation_density": 0.0,
            "digit_ratio": 0.0,
            "word_length_variation": 0.0,
        }

    words = tokenize_words(text)
    sentences = split_sentences(text)

    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "average_sentence_length": calculate_average_sentence_length(
            sentences
        ),
        "sentence_length_variance": calculate_sentence_length_variance(
            sentences
        ),
        "sentence_length_cv": calculate_sentence_length_cv(
            sentences
        ),
        "lexical_diversity": calculate_lexical_diversity(
            words
        ),
        "repetition_ratio": calculate_repetition_ratio(
            words
        ),
        "punctuation_density": calculate_punctuation_density(
            text
        ),
        "digit_ratio": calculate_digit_ratio(
            text
        ),
        "word_length_variation": calculate_word_length_variation(
            words
        ),
    }


# ---------------------------------------------------------------------------
# Heuristic baseline
# ---------------------------------------------------------------------------

def calculate_heuristic_ai_probability(
    signals: dict,
) -> tuple[float, float]:
    """
    Calculate a preliminary AI-likeness estimate.

    IMPORTANT:
    This is NOT a production-grade AI detector.

    It is only a deterministic offline baseline that
    converts linguistic signals into a probability-like
    value so the complete pipeline can be tested.

    The score must NOT be interpreted as proof that text
    was generated by AI.
    """

    word_count = signals["word_count"]

    if word_count < 50:
        return 0.0, 0.0

    score = 0.0

    # Extremely low sentence-length variation.
    cv = signals["sentence_length_cv"]

    if cv < 0.15:
        score += 0.20
    elif cv < 0.25:
        score += 0.10

    # Very high lexical repetition.
    repetition = signals["repetition_ratio"]

    if repetition > 0.45:
        score += 0.15
    elif repetition > 0.30:
        score += 0.08

    # Very low lexical diversity.
    diversity = signals["lexical_diversity"]

    if diversity < 0.35:
        score += 0.15
    elif diversity < 0.45:
        score += 0.08

    # Very regular word lengths.
    word_variation = signals["word_length_variation"]

    if word_variation < 0.35:
        score += 0.10

    # Very regular punctuation.
    punctuation_density = signals["punctuation_density"]

    if 0.025 <= punctuation_density <= 0.060:
        score += 0.10

    # Excessively long regular sentences.
    average_sentence_length = signals[
        "average_sentence_length"
    ]

    if average_sentence_length >= 28:
        score += 0.10

    # Extremely low variation combined with long sentences.
    if (
        average_sentence_length >= 22
        and cv < 0.20
    ):
        score += 0.10

    probability = clamp(score)

    # This is confidence in the heuristic calculation,
    # NOT confidence that the document is actually AI-generated.
    confidence = 0.35

    if word_count >= 100:
        confidence += 0.10

    if word_count >= 250:
        confidence += 0.10

    if word_count >= 500:
        confidence += 0.10

    confidence = clamp(confidence)

    return probability, confidence


# ---------------------------------------------------------------------------
# Complete document analysis
# ---------------------------------------------------------------------------

def analyze_scan_text(
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

        if not sentences:
            result.ai_probability = 0.0
            result.confidence = 0.0
            result.detected_signals = {
                "status": "INSUFFICIENT_TEXT",
                "word_count": 0,
                "sentence_count": 0,
            }
            result.status = "COMPLETED"
            result.completed_at = datetime.now(timezone.utc)

            db.flush()

            return result

        full_text = "\n".join(
            sentence.raw_text or ""
            for sentence in sentences
        )

        signals = extract_ai_signals(full_text)

        ai_probability, confidence = (
            calculate_heuristic_ai_probability(
                signals
            )
        )

        result.ai_probability = ai_probability
        result.confidence = confidence

        result.detected_signals = {
            "detector_type": "HEURISTIC_BASELINE",
            "algorithm_version": ALGORITHM_VERSION,
            "warning": (
                "This score is a preliminary linguistic "
                "heuristic and is not proof of AI generation."
            ),
            **signals,
        }

        result.status = "COMPLETED"
        result.completed_at = datetime.now(timezone.utc)

        db.flush()

        return result

    except Exception:
        result.status = "FAILED"
        result.completed_at = datetime.now(timezone.utc)

        db.flush()

        raise


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def run_ai_detection(
    db: Session,
    *,
    scan_id,
    initiated_by,
) -> AIDetectionResult:
    return analyze_scan_text(
        db=db,
        scan_id=scan_id,
        initiated_by=initiated_by,
    )