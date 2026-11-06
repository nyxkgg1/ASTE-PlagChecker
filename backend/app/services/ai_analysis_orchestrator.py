from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_analysis import AIAnalysisRun, AIDetectorResult
from app.models.model_registry import ModelRegistry
from app.models.scan import ScanSentence

from app.services.ai_authorship_classifier_service import (
    AIAuthorshipClassifierError,
    CLASSIFIER_MODEL_NAME,
    CLASSIFIER_MODEL_VERSION,
    classify_document,
    classify_sentences,
    SENTENCE_HIGHLIGHT_THRESHOLD,
)
from app.services.ai_analysis_run_service import (
    create_analysis_run,
    finalize_analysis_run,
)

from app.services.ai_detector_result_service import (
    create_detector_result,
    update_detector_result,
)

from app.services.ai_detector_evidence_service import (
    create_detector_evidence,
)

from app.services.ai_copy_matching_service import (
    search_ai_copy_matches,
)

from app.services.ai_detection_persistence_service import (
    calculate_document_ai_score,
)

from app.services.ai_source.ai_detection_service import (
    ALGORITHM_VERSION as HEURISTIC_VERSION,
    extract_ai_signals,
    calculate_heuristic_ai_probability,
)

from app.services.qwen_experimental_analysis_service import (
    DETECTOR_VERSION as QWEN_VERSION,
    analyze_writing_patterns,
)


CORPUS_VERSION = "1.0.0-AI-CORPUS"

logger = logging.getLogger(__name__)

def _run_qwen_detector(
    db: Session,
    *,
    run_id: UUID,
    sentences: list[ScanSentence],
) -> None:
    """
    Run qualitative Qwen analysis independently.

    A savepoint protects the rest of the analysis transaction from
    Qwen-specific failures. Qwen never produces a score or confidence.
    """

    result = create_detector_result(
        db,
        run_id=run_id,
        detector_type="QWEN_EXPERIMENTAL",
        detector_version=QWEN_VERSION,
        status="PROCESSING",
    )

    try:
        with db.begin_nested():
            analysis = analyze_writing_patterns(sentences)

            observations = analysis["observations"]

            for observation in observations:
                create_detector_evidence(
                    db,
                    detector_result_id=result.id,
                    sentence_id=UUID(observation["sentence_id"]),
                    evidence_type="QWEN_WRITING_OBSERVATION",
                    evidence_score=None,
                    details={
                        "category": observation["category"],
                        "observation": observation["observation"],
                        "quote": observation["quote"],
                        "sentence_index": observation["sentence_index"],
                    },
                )

            metrics = {
                "analysis_type": analysis["analysis_type"],
                "model": analysis["model"],
                "scope": analysis["scope"],
                "summary": analysis["summary"],
                "limitations": analysis["limitations"],
                "observation_count": len(observations),
            }

            update_detector_result(
                db,
                result_id=result.id,
                status="COMPLETED",
                score=None,
                confidence=None,
                metrics=metrics,
                explanation=analysis["summary"],
            )

    except Exception as exc:
        # The nested transaction has rolled back Qwen's evidence and
        # completion update. The outer analysis transaction remains usable.
        update_detector_result(
            db,
            result_id=result.id,
            status="FAILED",
            score=None,
            confidence=None,
            metrics={
                "error": "QWEN_ANALYSIS_FAILED",
                "error_type": type(exc).__name__,
            },
            explanation=(
                "Qualitative Qwen analysis could not be completed. "
                "No Qwen observations were saved. Other detector results "
                "are independent of this failure."
            ),
        )


def _run_heuristic_detector(
    db: Session,
    *,
    run_id: UUID,
    sentences: list[ScanSentence],
) -> None:

    result = create_detector_result(
        db,
        run_id=run_id,
        detector_type="LINGUISTIC_HEURISTIC",
        detector_version=HEURISTIC_VERSION,
        status="PROCESSING",
    )

    full_text = "\n".join(
        sentence.raw_text or ""
        for sentence in sentences
    )

    signals = extract_ai_signals(full_text)

    if signals["word_count"] < 50:
        update_detector_result(
            db,
            result_id=result.id,
            status="NOT_ANALYZED",
            metrics=signals,
            explanation=(
                "Insufficient text for the linguistic heuristic. "
                "At least 50 words are required by the current baseline."
            ),
        )
        return

    score, confidence = calculate_heuristic_ai_probability(
        signals
    )

    update_detector_result(
        db,
        result_id=result.id,
        status="COMPLETED",
        score=score * 100.0,
        confidence=confidence,
        metrics=signals,
        explanation=(
            "Preliminary linguistic indicator based on sentence-length "
            "variation, lexical diversity, repetition and other text "
            "features. This is not proof of AI authorship and is not a "
            "validated authorship probability."
        ),
    )


def _run_corpus_detector(
    db: Session,
    *,
    run_id: UUID,
    scan_id: UUID,
    sentences: list[ScanSentence],
) -> None:

    result = create_detector_result(
        db,
        run_id=run_id,
        detector_type="CORPUS_MATCH",
        detector_version=CORPUS_VERSION,
        status="PROCESSING",
    )

    source_type = (
        settings.ai_source_type or ""
    ).strip().upper()

    if source_type == "DATABASE":
        update_detector_result(
            db,
            result_id=result.id,
            status="NOT_CONFIGURED",
            metrics={
                "source_type": "DATABASE",
                "reason": "QUERY_RETRIEVAL_NOT_IMPLEMENTED",
            },
            explanation=(
                "The configured database source currently retrieves "
                "the first rows instead of searching for relevant text. "
                "Corpus analysis is disabled to prevent misleading results."
            ),
        )
        return

    if source_type != "DUMMY_LLAMA":
        update_detector_result(
            db,
            result_id=result.id,
            status="NOT_CONFIGURED",
            metrics={
                "source_type": source_type,
                "reason": "UNSUPPORTED_SOURCE_CONFIGURATION",
            },
            explanation=(
                "The configured AI corpus source is not supported by "
                "the current orchestrator."
            ),
        )
        return

    matches = search_ai_copy_matches(
        db=db,
        scan_id=scan_id,
    )

    match_map = {}

    for match in matches:
        sentence = match["scan_sentence"]
        match_map[sentence.id] = match

    sentence_results = []

    for sentence in sentences:
        match = match_map.get(sentence.id)

        sentence_result = {
            "sentence_id": str(sentence.id),
            "text_length": len(sentence.raw_text or ""),
            "match_score": 0.0,
            "match_method": None,
        }

        if match:
            sentence_result.update({
                "match_score": float(match["match_score"]),
                "match_method": match["match_method"],
            })

        sentence_results.append(sentence_result)

    document_metrics = calculate_document_ai_score(
        sentence_results
    )

    ai_copy_score = float(
        document_metrics["ai_copy_score"]
    )

    meaningful_matches = [
        match
        for match in matches
        if float(match.get("match_score", 0.0)) >= 0.50
    ]

    if document_metrics["exact_match_count"] > 0:
        confidence = 0.95
    elif (
        document_metrics["ngram_match_count"] > 0
        and document_metrics["semantic_match_count"] > 0
    ):
        confidence = 0.85
    elif document_metrics["semantic_match_count"] > 0:
        confidence = 0.70
    elif meaningful_matches:
        confidence = 0.50
    else:
        confidence = None

    metrics = {
        **document_metrics,
        "source_type": "DUMMY_LLAMA",
        "development_only": True,
    }

    update_detector_result(
        db,
        result_id=result.id,
        status="COMPLETED",
        score=ai_copy_score * 100.0,
        confidence=confidence,
        metrics=metrics,
        explanation=(
            "Measures the proportion of submitted text matched against "
            "the configured development corpus. This is corpus similarity, "
            "not a measure or proof of AI authorship. The current source "
            "contains demonstration documents only."
        ),
    )

    for match in matches:
        sentence = match["scan_sentence"]

        evidence_details = {
            "source_id": str(match.get("source_id", "")),
            "match_method": match.get("match_method"),
            "exact_score": float(match.get("exact_score", 0.0)),
            "ngram_score": float(match.get("ngram_score", 0.0)),
            "tfidf_score": float(match.get("tfidf_score", 0.0)),
            "semantic_score": float(match.get("semantic_score", 0.0)),
            "source_metadata": match.get("metadata") or {},
        }

        create_detector_evidence(
            db,
            detector_result_id=result.id,
            sentence_id=sentence.id,
            evidence_type="CORPUS_TEXT_MATCH",
            evidence_score=float(match["match_score"]) * 100.0,
            details=evidence_details,
        )


def _run_classifier_detector(
    db: Session,
    *,
    run_id: UUID,
    sentences: list[ScanSentence],
) -> None:
    models = (
        db.query(ModelRegistry)
        .filter(
            ModelRegistry.model_name == CLASSIFIER_MODEL_NAME,
            ModelRegistry.version == CLASSIFIER_MODEL_VERSION,
            ModelRegistry.model_type == "CLASSIFIER",
            ModelRegistry.is_active.is_(True),
        )
        .all()
    )

    if not models:
        create_detector_result(
            db,
            run_id=run_id,
            detector_type="CLASSIFIER",
            detector_version=CLASSIFIER_MODEL_VERSION,
            status="NOT_CONFIGURED",
            explanation=(
                "The local AI-authorship classifier is not installed or "
                "registered. Run the classifier setup script to enable it."
            ),
        )
        return

    if len(models) != 1:
        create_detector_result(
            db,
            run_id=run_id,
            detector_type="CLASSIFIER",
            detector_version=CLASSIFIER_MODEL_VERSION,
            status="FAILED",
            explanation=(
                "More than one active registration exists for the configured "
                "AI-authorship classifier. Keep exactly one active model."
            ),
        )
        logger.error(
            "Expected one active %s classifier registration; found %d.",
            CLASSIFIER_MODEL_NAME,
            len(models),
        )
        return

    model = models[0]
    create_detector_result(
        db,
        run_id=run_id,
        detector_type="CLASSIFIER",
        detector_version=CLASSIFIER_MODEL_VERSION,
        status="PROCESSING",
        model_id=model.id,
    )

    result = (
        db.query(AIDetectorResult)
        .filter(
            AIDetectorResult.run_id == run_id,
            AIDetectorResult.detector_type == "CLASSIFIER",
        )
        .one()
    )
    document_text = "\n".join(
        sentence.raw_text or ""
        for sentence in sentences
        if sentence.raw_text and sentence.raw_text.strip()
    )

    try:
        with db.begin_nested():
            classification = classify_document(
                document_text,
                model_path=model.local_path,
            )
            probability = classification["ai_probability"]
            if not 0 <= probability <= 1:
                raise AIAuthorshipClassifierError(
                    "The classifier probability is outside the [0, 1] range."
                )
            model_confidence = max(probability, 1 - probability)
            sentence_analysis_status = "COMPLETED"
            sentence_analysis_error = None
            try:
                sentence_probabilities = classify_sentences(
                    [
                        sentence.raw_text
                        for sentence in sentences
                        if sentence.raw_text and sentence.raw_text.strip()
                    ],
                    model_path=model.local_path,
                )
            except AIAuthorshipClassifierError as exc:
                logger.exception(
                    "Sentence-level classifier analysis failed for run %s.",
                    run_id,
                )
                sentence_probabilities = []
                sentence_analysis_status = "FAILED"
                sentence_analysis_error = str(exc)

            source_sentences = [
                sentence
                for sentence in sentences
                if sentence.raw_text and sentence.raw_text.strip()
            ]
            sentence_results = (
                zip(source_sentences, sentence_probabilities, strict=True)
                if sentence_analysis_status == "COMPLETED"
                else ()
            )
            for sentence, sentence_probability in sentence_results:
                if sentence_probability < SENTENCE_HIGHLIGHT_THRESHOLD:
                    continue
                create_detector_evidence(
                    db,
                    detector_result_id=result.id,
                    sentence_id=sentence.id,
                    evidence_type="AI_PATTERN_SENTENCE",
                    evidence_score=sentence_probability * 100,
                    details={
                        "ai_probability": sentence_probability,
                        "model_confidence": max(
                            sentence_probability,
                            1 - sentence_probability,
                        ),
                        "visualization_threshold": SENTENCE_HIGHLIGHT_THRESHOLD,
                        "interpretation": (
                            "Experimental sentence-level classifier signal; "
                            "not proof of AI authorship."
                        ),
                    },
                )

            update_detector_result(
                db,
                result_id=result.id,
                status="COMPLETED",
                score=probability * 100,
                confidence=model_confidence,
                metrics={
                    **classification,
                    "model_confidence": model_confidence,
                    "sentence_analysis_status": sentence_analysis_status,
                    "sentence_analysis_error": sentence_analysis_error,
                    "sentence_highlight_threshold": SENTENCE_HIGHLIGHT_THRESHOLD,
                    "ai_pattern_sentences_highlighted": sum(
                        score >= SENTENCE_HIGHLIGHT_THRESHOLD
                        for score in sentence_probabilities
                    ),
                    "model_name": model.model_name,
                    "model_version": model.version,
                    "interpretation": (
                        "Model-generated AI-likelihood indicator; not "
                        "proof of authorship. Model confidence is its "
                        "top-class softmax output, not validated accuracy "
                        "or calibrated certainty for this document domain."
                    ),
                },
                explanation=(
                    "Advisory AI-likelihood score from a locally hosted "
                    "English-language classifier. Results can be wrong, "
                    "especially for domains unlike the model's training "
                    "data; do not use as sole evidence for academic penalties."
                ),
            )
    except Exception as exc:
        logger.exception(
            "AI-authorship classification failed for analysis run %s.",
            run_id,
        )
        update_detector_result(
            db,
            result_id=result.id,
            status="FAILED",
            metrics={
                "error": "AI_CLASSIFIER_FAILED",
                "error_type": type(exc).__name__,
            },
            explanation=(
                "The local AI-authorship classifier failed to process this "
                "document. No classifier score was generated."
            ),
        )


def run_ai_analysis(
    db: Session,
    *,
    scan_id: UUID,
    initiated_by: UUID,
) -> AIAnalysisRun:
    """
    Execute the currently available AI detectors for one scan.

    Each detector is persisted independently. A failure in one
    detector does not prevent the other detectors from running.

    The caller owns the transaction. This function does not commit.
    """

    run = create_analysis_run(
        db,
        scan_id=scan_id,
        initiated_by=initiated_by,
    )

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

    _run_classifier_detector(
        db,
        run_id=run.id,
        sentences=sentences,
    )

    try:
        _run_corpus_detector(
            db,
            run_id=run.id,
            scan_id=scan_id,
            sentences=sentences,
        )
    except Exception as exc:
        corpus_result = (
            next(
                (
                    item
                    for item in run.detector_results
                    if item.detector_type == "CORPUS_MATCH"
                ),
                None,
            )
        )

        if corpus_result and corpus_result.status == "PROCESSING":
            update_detector_result(
                db,
                result_id=corpus_result.id,
                status="FAILED",
                explanation=f"Corpus detector failed: {exc}",
            )

    try:
        _run_heuristic_detector(
            db,
            run_id=run.id,
            sentences=sentences,
        )
    except Exception as exc:
        heuristic_result = (
            next(
                (
                    item
                    for item in run.detector_results
                    if item.detector_type == "LINGUISTIC_HEURISTIC"
                ),
                None,
            )
        )

        if heuristic_result and heuristic_result.status == "PROCESSING":
            update_detector_result(
                db,
                result_id=heuristic_result.id,
                status="FAILED",
                explanation=f"Linguistic heuristic failed: {exc}",
            )

    _run_qwen_detector(
        db,
        run_id=run.id,
        sentences=sentences,
    )

    return finalize_analysis_run(
        db,
        run_id=run.id,
    )
