from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.scan import ScanSentence
from app.services.ai_source.factory import get_ai_content_source
from app.services.ai_source.base import AISourceDocument
from app.services.plagiarism_fingerprint_service import (
    exact_text_similarity,
    ngram_similarity,
)
from app.services.tfidf_similarity_service import (
    calculate_tfidf_similarity,
)
from app.services.embedding_service import (
    generate_embedding,
    generate_embeddings,
)


AI_SEMANTIC_THRESHOLD = 0.70
AI_STRONG_SEMANTIC_THRESHOLD = 0.85

MAX_AI_CANDIDATES_PER_SENTENCE = 10
AI_EMBEDDING_BATCH_SENTENCES = 64


def _cosine_similarity(
    embedding_a: list[float],
    embedding_b: list[float],
) -> float:
    if not embedding_a or not embedding_b:
        return 0.0

    if len(embedding_a) != len(embedding_b):
        return 0.0

    dot_product = sum(
        a * b
        for a, b in zip(
            embedding_a,
            embedding_b,
        )
    )

    magnitude_a = sum(
        value * value
        for value in embedding_a
    ) ** 0.5

    magnitude_b = sum(
        value * value
        for value in embedding_b
    ) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return max(
        0.0,
        min(
            1.0,
            dot_product / (
                magnitude_a * magnitude_b
            ),
        ),
    )


def calculate_semantic_similarity(
    text_a: str,
    text_b: str,
) -> float:

    embedding_a = generate_embedding(text_a)
    embedding_b = generate_embedding(text_b)

    return _cosine_similarity(embedding_a, embedding_b)


def compare_ai_candidate(
    scan_sentence: ScanSentence,
    ai_document: AISourceDocument,
    embedding_by_text: dict[str, list[float]] | None = None,
) -> dict:

    scan_text = (
        scan_sentence.normalized_text
        or scan_sentence.raw_text
        or ""
    )

    ai_text = ai_document.text or ""

    exact_score = exact_text_similarity(
        scan_text,
        ai_text,
    )

    ngram_score = ngram_similarity(
        scan_text,
        ai_text,
        n=5,
    )

    tfidf_score = calculate_tfidf_similarity(
        scan_text,
        ai_text,
    )

    if embedding_by_text is None:
        semantic_score = calculate_semantic_similarity(
            scan_text,
            ai_text,
        )
    else:
        semantic_score = _cosine_similarity(
            embedding_by_text.get(scan_text, []),
            embedding_by_text.get(ai_text, []),
        )

    return {
        "source_id": ai_document.source_id,
        "text": ai_document.text,
        "metadata": ai_document.metadata,
        "exact_score": exact_score,
        "ngram_score": ngram_score,
        "tfidf_score": tfidf_score,
        "semantic_score": semantic_score,
    }


def calculate_ai_match_score(
    result: dict,
) -> tuple[float, str]:

    exact_score = float(
        result.get("exact_score", 0.0)
    )

    ngram_score = float(
        result.get("ngram_score", 0.0)
    )

    tfidf_score = float(
        result.get("tfidf_score", 0.0)
    )

    semantic_score = float(
        result.get("semantic_score", 0.0)
    )

    # Exact match is definitive corpus evidence.
    if exact_score >= 1.0:
        return 1.0, "EXACT"

    # Strong textual overlap.
    if ngram_score >= 0.80:
        return ngram_score, "NGRAM"

    # Combination of lexical and semantic evidence.
    combined_score = (
        0.25 * ngram_score
        + 0.20 * tfidf_score
        + 0.55 * semantic_score
    )

    if semantic_score >= AI_STRONG_SEMANTIC_THRESHOLD:
        if (
            tfidf_score >= 0.20
            or ngram_score >= 0.10
        ):
            return combined_score, "SEMANTIC"

    if tfidf_score >= 0.65:
        return combined_score, "TFIDF"

    if ngram_score >= 0.35:
        return combined_score, "NGRAM"

    return combined_score, "LOW"


def find_ai_matches_for_sentence(
    db: Session,
    scan_sentence: ScanSentence,
    source,
    ai_candidates: list[AISourceDocument] | None = None,
    embedding_by_text: dict[str, list[float]] | None = None,
) -> list[dict]:
    if ai_candidates is None:
        ai_candidates = source.search(
            query_text=scan_sentence.raw_text or "",
            limit=MAX_AI_CANDIDATES_PER_SENTENCE,
        )

    if not ai_candidates:
        return []

    results = []

    for ai_document in ai_candidates:

        if not ai_document.text:
            continue

        result = compare_ai_candidate(
            scan_sentence=scan_sentence,
            ai_document=ai_document,
            embedding_by_text=embedding_by_text,
        )

        score, method = calculate_ai_match_score(
            result
        )

        result["match_score"] = score
        result["match_method"] = method

        # Do not treat semantic similarity by itself
        # as evidence of AI-originated content.
        strong_textual_evidence = (
            result["exact_score"] >= 0.80
            or result["ngram_score"] >= 0.40
            or result["tfidf_score"] >= 0.50
        )

        strong_semantic_evidence = (
            result["semantic_score"]
            >= AI_STRONG_SEMANTIC_THRESHOLD
            and (
                result["tfidf_score"] >= 0.20
                or result["ngram_score"] >= 0.10
            )
        )

        if (
            strong_textual_evidence
            or strong_semantic_evidence
        ):
            results.append(result)

    results.sort(
        key=lambda item: item["match_score"],
        reverse=True,
    )

    return results


def search_ai_copy_matches(
    db: Session,
    scan_id,
) -> list[dict]:

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

    all_matches = []

    if not sentences:
        return []

    source = get_ai_content_source(db)

    for batch_start in range(
        0,
        len(sentences),
        AI_EMBEDDING_BATCH_SENTENCES,
    ):
        sentence_batch = sentences[
            batch_start:batch_start + AI_EMBEDDING_BATCH_SENTENCES
        ]
        candidates_by_sentence = [
            source.search(
                query_text=sentence.raw_text or "",
                limit=MAX_AI_CANDIDATES_PER_SENTENCE,
            )
            for sentence in sentence_batch
        ]

        texts = dict.fromkeys(
            text
            for sentence, candidates in zip(
                sentence_batch,
                candidates_by_sentence,
                strict=True,
            )
            for text in [
                sentence.normalized_text or sentence.raw_text or "",
                *(
                    candidate.text or ""
                    for candidate in candidates
                ),
            ]
            if text.strip()
        )
        unique_texts = list(texts)
        vectors = generate_embeddings(unique_texts)
        embedding_by_text = dict(
            zip(unique_texts, vectors, strict=True)
        )

        for sentence, candidates in zip(
            sentence_batch,
            candidates_by_sentence,
            strict=True,
        ):
            sentence_matches = find_ai_matches_for_sentence(
                db=db,
                scan_sentence=sentence,
                source=source,
                ai_candidates=candidates,
                embedding_by_text=embedding_by_text,
            )
            if not sentence_matches:
                continue

            all_matches.append(
                {
                    "scan_sentence": sentence,
                    **sentence_matches[0],
                }
            )

    all_matches.sort(
        key=lambda item: item["match_score"],
        reverse=True,
    )

    return all_matches