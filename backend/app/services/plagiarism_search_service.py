from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.plagiarism_fingerprint import ReferenceSentenceFingerprint
from app.services.plagiarism_fingerprint_service import (
    character_similarity,
    exact_text_similarity,
    generate_ngram_fingerprints,
    generate_character_ngram_fingerprints,
    ngram_similarity,
)
from app.models.reference import ReferenceDocument, ReferenceSentence
from app.models.scan import ScanSentence

from app.services.plagiarism_fingerprint_service import (
    exact_text_similarity,
    generate_ngram_fingerprints,
    ngram_similarity,
)

from app.services.reference_embedding_search_service import (
    search_reference_embeddings,
)

from app.services.tfidf_similarity_service import (
    calculate_tfidf_similarity,
)
from app.services.plagiarism_exclusion_service import (
    get_plagiarism_exclusions,
    remove_excluded_text,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_NGRAM_SIZES = (3, 5)

# Maximum number of lexical candidates for one scan sentence.
MAX_CANDIDATES_PER_SENTENCE = 20

# Maximum number of semantic candidates for one scan sentence.
MAX_SEMANTIC_CANDIDATES_PER_SENTENCE = 10

# Minimum semantic similarity required for a reference sentence
# to become a semantic candidate.
CANDIDATE_SEMANTIC_THRESHOLD = 0.55

# Very short sentences/fragments should generally not be
# considered for plagiarism detection.
#
# Examples:
#   14
#   4.4.
#   Table 1.
#   Yes.
MIN_PLAGIARISM_TOKENS = 5


# ============================================================
# TEXT VALIDATION
# ============================================================

def has_minimum_tokens(
    text: str,
    minimum: int = MIN_PLAGIARISM_TOKENS,
) -> bool:
    """
    Check whether text contains enough whitespace-separated
    tokens to perform meaningful plagiarism comparison.

    This is intentionally calculated from the text rather than
    using ReferenceSentence.token_count because the current
    ReferenceSentence model does not contain a token_count field.
    """

    if not text:
        return False

    tokens = text.split()

    return len(tokens) >= minimum


# ============================================================
# LEXICAL CANDIDATE SEARCH
# ============================================================
# LEXICAL CANDIDATE SEARCH
# ============================================================

def find_fingerprint_candidates(
    db: Session,
    scan_sentence: ScanSentence,
    excluded_words: list[str] | None = None,
    excluded_phrases: list[str] | None = None,
) -> list[ReferenceSentence]:
    """
    Retrieve lexical candidates through separate WORD and CHARACTER
    fingerprint rankings, then merge both rankings fairly.

    Character fingerprints are for candidate retrieval only. Final
    plagiarism scoring and evidence-acceptance rules are unchanged.
    """

    scan_text = scan_sentence.normalized_text or ""
    filtered_text = remove_excluded_text(
        scan_text,
        excluded_words or [],
        excluded_phrases or [],
    )

    if not has_minimum_tokens(filtered_text):
        return []

    word_scores: defaultdict[str, int] = defaultdict(int)
    character_scores: defaultdict[str, int] = defaultdict(int)

    # --------------------------------------------------------
    # 1. WORD fingerprint candidates
    # --------------------------------------------------------

    for ngram_size in DEFAULT_NGRAM_SIZES:
        fingerprints = generate_ngram_fingerprints(
            scan_text,
            n=ngram_size,
        )

        if not fingerprints:
            continue

        rows = (
            db.query(
                ReferenceSentenceFingerprint.reference_sentence_id,
            )
            .join(
                ReferenceSentence,
                ReferenceSentence.id
                == ReferenceSentenceFingerprint.reference_sentence_id,
            )
            .join(
                ReferenceDocument,
                ReferenceDocument.id
                == ReferenceSentence.reference_document_id,
            )
            .filter(
                ReferenceSentenceFingerprint.fingerprint_type == "WORD",
                ReferenceSentenceFingerprint.ngram_size == ngram_size,
                ReferenceSentenceFingerprint.fingerprint_hash.in_(
                    fingerprints
                ),
                ReferenceDocument.status == "ACTIVE",
            )
            .all()
        )

        for row in rows:
            word_scores[str(row.reference_sentence_id)] += 1

    # --------------------------------------------------------
    # 2. CHARACTER fingerprint candidates
    # --------------------------------------------------------

    min_shared_character_fingerprints = 8
    character_ngram_size = 4

    character_fingerprints = generate_character_ngram_fingerprints(
        scan_text,
        n=character_ngram_size,
    )

    if character_fingerprints:
        character_rows = (
            db.query(
                ReferenceSentenceFingerprint.reference_sentence_id,
            )
            .join(
                ReferenceSentence,
                ReferenceSentence.id
                == ReferenceSentenceFingerprint.reference_sentence_id,
            )
            .join(
                ReferenceDocument,
                ReferenceDocument.id
                == ReferenceSentence.reference_document_id,
            )
            .filter(
                ReferenceSentenceFingerprint.fingerprint_type == "CHARACTER",
                ReferenceSentenceFingerprint.ngram_size
                == character_ngram_size,
                ReferenceSentenceFingerprint.fingerprint_hash.in_(
                    character_fingerprints
                ),
                ReferenceDocument.status == "ACTIVE",
            )
            .all()
        )

        for row in character_rows:
            character_scores[str(row.reference_sentence_id)] += 1

    # Keep the existing minimum-overlap requirement.
    character_scores = defaultdict(
        int,
        {
            reference_id: count
            for reference_id, count in character_scores.items()
            if count >= min_shared_character_fingerprints
        },
    )

    if not word_scores and not character_scores:
        return []

    # --------------------------------------------------------
    # 3. Rank WORD and CHARACTER candidates independently
    # --------------------------------------------------------

    ranked_word_ids = sorted(
        word_scores,
        key=lambda reference_id: (-word_scores[reference_id], reference_id),
    )

    ranked_character_ids = sorted(
        character_scores,
        key=lambda reference_id: (
            -character_scores[reference_id],
            reference_id,
        ),
    )

    # --------------------------------------------------------
    # 4. Interleave the rankings to protect both retrieval paths
    # --------------------------------------------------------

    ranked_ids = []
    seen_ids = set()
    max_pool_size = MAX_CANDIDATES_PER_SENTENCE

    for index in range(max_pool_size):
        for ranked_pool in (ranked_word_ids, ranked_character_ids):
            if index >= len(ranked_pool):
                continue

            reference_id = ranked_pool[index]

            if reference_id not in seen_ids:
                ranked_ids.append(reference_id)
                seen_ids.add(reference_id)

            if len(ranked_ids) >= max_pool_size:
                break

        if len(ranked_ids) >= max_pool_size:
            break

    if not ranked_ids:
        return []

    # Filter short references BEFORE returning the final capped list,
    # so short fragments cannot consume candidate slots.
    references = (
        db.query(ReferenceSentence)
        .join(
            ReferenceDocument,
            ReferenceDocument.id
            == ReferenceSentence.reference_document_id,
        )
        .filter(ReferenceSentence.id.in_(ranked_ids))
        .filter(ReferenceDocument.status == "ACTIVE")
        .all()
    )

    reference_map = {
        str(reference.id): reference
        for reference in references
        if has_minimum_tokens(reference.normalized_text or "")
    }

    return [
        reference_map[reference_id]
        for reference_id in ranked_ids
        if reference_id in reference_map
    ]


# ============================================================
# LEXICAL COMPARISON
# ============================================================


def compare_lexical_candidate(
    scan_sentence: ScanSentence,
    reference: ReferenceSentence,
    excluded_words: list[str] | None = None,
    excluded_phrases: list[str] | None = None,
) -> dict:
    """
    Compare one scan sentence against one reference sentence.

    Character similarity is collected for diagnostics only.
    Existing matching and acceptance rules remain unchanged.
    """
    scan_text = remove_excluded_text(
        scan_sentence.normalized_text or "",
        excluded_words or [],
        excluded_phrases or [],
    )
    reference_text = remove_excluded_text(
        reference.normalized_text or "",
        excluded_words or [],
        excluded_phrases or [],
    )
    if not has_minimum_tokens(scan_text) or not has_minimum_tokens(reference_text):
        return {
            "reference": reference,
            "exact_score": 0.0,
            "ngram_score": 0.0,
            "tfidf_score": 0.0,
            "character_score": 0.0,
        }

    exact_score = exact_text_similarity(scan_text, reference_text)

    ngram_score = ngram_similarity(
        scan_text,
        reference_text,
        n=5,
    )

    tfidf_score = calculate_tfidf_similarity(
        scan_text,
        reference_text,
    )

    character_score = character_similarity(
        scan_text,
        reference_text,
    )

    return {
        "reference": reference,
        "exact_score": float(exact_score),
        "ngram_score": float(ngram_score),
        "tfidf_score": float(tfidf_score),
        "character_score": float(character_score),
    }



# ============================================================
# SEMANTIC CANDIDATE SEARCH
# ============================================================

def find_semantic_candidates(
    db: Session,
    scan_sentence: ScanSentence,
    excluded_words: list[str] | None = None,
    excluded_phrases: list[str] | None = None,
) -> list[dict]:
    """
    Search the reference embedding index for semantically similar
    reference sentences.

    Semantic similarity is used for candidate generation.

    Semantic similarity alone is NOT sufficient evidence of
    plagiarism.
    """

    filtered_text = remove_excluded_text(
        scan_sentence.normalized_text or "",
        excluded_words or [],
        excluded_phrases or [],
    )
    if not has_minimum_tokens(filtered_text):
        return []

    results = search_reference_embeddings(
        db=db,
        query_text=scan_sentence.raw_text,
        limit=MAX_SEMANTIC_CANDIDATES_PER_SENTENCE,
        min_similarity=CANDIDATE_SEMANTIC_THRESHOLD,
    )

    return results or []


# ============================================================
# COMBINED CANDIDATE EVIDENCE
# ============================================================

def build_combined_match(
    lexical_result: dict | None,
    semantic_result: dict | None,
) -> dict:
    """
    Combine lexical and semantic evidence for one candidate.

    This function produces the evidence values.

    Final evidence acceptance is handled separately by
    has_significant_evidence().
    """

    if (
        lexical_result is None
        and semantic_result is None
    ):
        return {}

    # --------------------------------------------------------
    # Lexical scores
    # --------------------------------------------------------

    if lexical_result is not None:

        reference = lexical_result.get("reference")

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

    else:

        reference = None

        exact_score = 0.0
        ngram_score = 0.0
        tfidf_score = 0.0

    # --------------------------------------------------------
    # Semantic score
    # --------------------------------------------------------

    semantic_score = 0.0

    if semantic_result is not None:

        semantic_score = float(
            semantic_result.get(
                "similarity",
                0.0,
            )
        )

    # --------------------------------------------------------
    # Preliminary score
    # --------------------------------------------------------

    if exact_score >= 1.0:

        final_score = 1.0
        method = "EXACT"

    elif ngram_score >= 0.80:

        final_score = ngram_score
        method = "NGRAM"

    else:

        # Conservative combination.
        #
        # Semantic similarity receives significant weight for
        # paraphrases, but lexical evidence is still required
        # later by has_significant_evidence().

        final_score = (
            (0.30 * ngram_score)
            + (0.25 * tfidf_score)
            + (0.45 * semantic_score)
        )

        if (
            semantic_score >= 0.85
            and (
                tfidf_score >= 0.20
                or ngram_score >= 0.10
            )
        ):
            method = "SEMANTIC"

        elif ngram_score >= tfidf_score:
            method = "NGRAM"

        else:
            method = "TFIDF"

    return {
        "reference": reference,
        "exact_score": exact_score,
        "ngram_score": ngram_score,
        "tfidf_score": tfidf_score,
        "semantic_score": semantic_score,
        "final_score": max(
            0.0,
            min(1.0, float(final_score)),
        ),
        "method": method,
    }


# ============================================================
# SIGNIFICANT EVIDENCE FILTER
# ============================================================

def has_significant_evidence(
    *,
    exact_score: float,
    ngram_score: float,
    tfidf_score: float,
    semantic_score: float,
) -> bool:
    """
    Determine whether a candidate has enough evidence to be
    treated as a significant plagiarism match.

    IMPORTANT:

    Semantic similarity alone is deliberately NOT sufficient.

    This prevents semantically related but independently written
    technical content from automatically becoming plagiarism.
    """

    # --------------------------------------------------------
    # 1. Strong exact/textual evidence
    # --------------------------------------------------------

    if exact_score >= 0.80:
        return True

    # --------------------------------------------------------
    # 2. Strong n-gram overlap
    # --------------------------------------------------------

    if ngram_score >= 0.40:
        return True

    # --------------------------------------------------------
    # 3. Strong TF-IDF similarity
    # --------------------------------------------------------

    if tfidf_score >= 0.50:
        return True

    # --------------------------------------------------------
    # 4. Strong semantic similarity + textual evidence
    # --------------------------------------------------------

    if semantic_score >= 0.85:

        if tfidf_score >= 0.20:
            return True

        if ngram_score >= 0.10:
            return True

    # --------------------------------------------------------
    # 5. Moderate semantic similarity requires stronger
    #    lexical evidence.
    # --------------------------------------------------------

    if semantic_score >= 0.75:

        if (
            tfidf_score >= 0.30
            and ngram_score >= 0.15
        ):
            return True

    return False


# ============================================================
# MATCH CLASSIFICATION
# ============================================================

def determine_match_type(
    *,
    exact_score: float,
    ngram_score: float,
    tfidf_score: float,
    semantic_score: float,
) -> str:
    """
    Convert individual evidence scores into a match category.
    """

    # --------------------------------------------------------
    # Exact
    # --------------------------------------------------------

    if exact_score >= 1.0:
        return "EXACT"

    # --------------------------------------------------------
    # Strong textual match
    # --------------------------------------------------------

    if (
        ngram_score >= 0.80
        or (
            ngram_score >= 0.45
            and tfidf_score >= 0.50
        )
    ):
        return "STRONG_TEXTUAL_MATCH"

    # --------------------------------------------------------
    # High similarity
    # --------------------------------------------------------

    if (
        semantic_score >= 0.85
        and (
            tfidf_score >= 0.20
            or ngram_score >= 0.10
        )
    ):
        return "HIGH_SIMILARITY"

    # --------------------------------------------------------
    # Moderate similarity
    # --------------------------------------------------------

    if (
        semantic_score >= 0.75
        and tfidf_score >= 0.30
    ):
        return "MODERATE_SIMILARITY"

    # --------------------------------------------------------
    # Low similarity
    # --------------------------------------------------------

    if (
        ngram_score >= 0.25
        or tfidf_score >= 0.35
    ):
        return "LOW_SIMILARITY"

    return "NO_SIGNIFICANT_MATCH"


# ============================================================
# MAIN PLAGIARISM SEARCH
# ============================================================

def search_plagiarism_candidates(
    db: Session,
    scan_id,
    excluded_words: list[str] | None = None,
    excluded_phrases: list[str] | None = None,
) -> list[dict]:
    """
    Main plagiarism candidate generation and verification
    pipeline.

    Flow:

        Scan sentence
             |
             +---- Fingerprint search
             |
             +---- Qwen3 semantic search
             |
             v
        Candidate union
             |
             v
        Detailed comparison
             |
             v
        Evidence filtering
             |
             v
        Significant matches
    """

    # ========================================================
    # Load scan sentences
    # ========================================================

    if excluded_words is None or excluded_phrases is None:
        stored_words, stored_phrases = get_plagiarism_exclusions(db)
        excluded_words = excluded_words or stored_words
        excluded_phrases = excluded_phrases or stored_phrases

    scan_sentences = (
        db.query(ScanSentence)
        .filter(
            ScanSentence.scan_id == scan_id,
            ScanSentence.token_count >= MIN_PLAGIARISM_TOKENS,
        )
        .order_by(
            ScanSentence.page_id,
            ScanSentence.sentence_index,
        )
        .all()
    )

    matches: list[dict] = []

    # ========================================================
    # Process each scan sentence
    # ========================================================

    for scan_sentence in scan_sentences:
        filtered_scan_text = remove_excluded_text(
            scan_sentence.normalized_text or "",
            excluded_words,
            excluded_phrases,
        )
        if not has_minimum_tokens(filtered_scan_text):
            continue

        # ----------------------------------------------------
        # 1. Lexical candidate generation
        # ----------------------------------------------------

        lexical_candidates = find_fingerprint_candidates(
            db=db,
            scan_sentence=scan_sentence,
            excluded_words=excluded_words,
            excluded_phrases=excluded_phrases,
        )

        lexical_results: dict[str, dict] = {}

        for reference in lexical_candidates:

            result = compare_lexical_candidate(
                scan_sentence=scan_sentence,
                reference=reference,
                excluded_words=excluded_words,
                excluded_phrases=excluded_phrases,
            )

            lexical_results[
                str(reference.id)
            ] = result

        # ----------------------------------------------------
        # 2. Semantic candidate generation
        # ----------------------------------------------------

        semantic_candidates = find_semantic_candidates(
            db=db,
            scan_sentence=scan_sentence,
            excluded_words=excluded_words,
            excluded_phrases=excluded_phrases,
        )

        semantic_results: dict[str, dict] = {}

        for result in semantic_candidates:

            sentence_id = result.get(
                "sentence_id"
            )

            if sentence_id is None:
                continue

            semantic_results[
                str(sentence_id)
            ] = result

        # ----------------------------------------------------
        # 3. Combine lexical + semantic candidate IDs
        # ----------------------------------------------------

        candidate_ids = (
            set(lexical_results.keys())
            | set(semantic_results.keys())
        )

        if not candidate_ids:
            continue

        # ----------------------------------------------------
        # 4. Detailed comparison
        # ----------------------------------------------------

        for candidate_id in candidate_ids:

            lexical_result = lexical_results.get(
                candidate_id
            )

            semantic_result = semantic_results.get(
                candidate_id
            )

            # ------------------------------------------------
            # Semantic-only candidate
            # ------------------------------------------------

            if lexical_result is None:

                reference = (
                    db.query(ReferenceSentence)
                    .filter(
                        ReferenceSentence.id
                        == candidate_id
                    )
                    .first()
                )

                if reference is None:
                    continue

                # ReferenceSentence has no token_count field.
                if not has_minimum_tokens(
                    remove_excluded_text(
                        reference.normalized_text or "",
                        excluded_words,
                        excluded_phrases,
                    )
                ):
                    continue

                lexical_result = {
                    "reference": reference,
                    "exact_score": 0.0,
                    "ngram_score": 0.0,
                    "tfidf_score": 0.0,
                }

            # ------------------------------------------------
            # Combine evidence
            # ------------------------------------------------

            reference = (
                lexical_result.get("reference")
                if lexical_result is not None
                else None
            )
            reference_text = (
                remove_excluded_text(
                    reference.normalized_text or "",
                    excluded_words,
                    excluded_phrases,
                )
                if reference is not None
                else ""
            )
            scan_contains_exclusions = (
                filtered_scan_text.casefold()
                != (scan_sentence.normalized_text or "").casefold()
            )
            reference_contains_exclusions = (
                reference is not None
                and reference_text.casefold()
                != (reference.normalized_text or "").casefold()
            )
            if scan_contains_exclusions or reference_contains_exclusions:
                semantic_result = None

            combined = build_combined_match(
                lexical_result=lexical_result,
                semantic_result=semantic_result,
            )

            if not combined:
                continue

            reference = combined.get(
                "reference"
            )

            if reference is None:
                continue

            # ------------------------------------------------
            # Extract scores
            # ------------------------------------------------

            exact_score = float(
                combined.get(
                    "exact_score",
                    0.0,
                )
            )

            ngram_score = float(
                combined.get(
                    "ngram_score",
                    0.0,
                )
            )

            tfidf_score = float(
                combined.get(
                    "tfidf_score",
                    0.0,
                )
            )

            semantic_score = float(
                combined.get(
                    "semantic_score",
                    0.0,
                )
            )

            # ------------------------------------------------
            # Evidence validation
            # ------------------------------------------------

            if not has_significant_evidence(
                exact_score=exact_score,
                ngram_score=ngram_score,
                tfidf_score=tfidf_score,
                semantic_score=semantic_score,
            ):
                continue

            # ------------------------------------------------
            # Classification
            # ------------------------------------------------

            match_type = determine_match_type(
                exact_score=exact_score,
                ngram_score=ngram_score,
                tfidf_score=tfidf_score,
                semantic_score=semantic_score,
            )

            if match_type == "NO_SIGNIFICANT_MATCH":
                continue

            # ------------------------------------------------
            # Final similarity score
            # ------------------------------------------------

            if exact_score >= 1.0:

                similarity_score = 1.0

            elif ngram_score >= 0.80:

                similarity_score = ngram_score

            else:

                similarity_score = (
                    (0.30 * ngram_score)
                    + (0.25 * tfidf_score)
                    + (0.45 * semantic_score)
                )

            similarity_score = max(
                0.0,
                min(
                    1.0,
                    float(similarity_score),
                ),
            )

            # ------------------------------------------------
            # Store candidate
            # ------------------------------------------------

            matches.append(
                {
                    "scan_sentence": scan_sentence,
                    "reference_sentence": reference,
                    "exact_score": exact_score,
                    "ngram_score": ngram_score,
                    "tfidf_score": tfidf_score,
                    "semantic_score": semantic_score,
                    "similarity_score": similarity_score,
                    "method": match_type,
                }
            )

    # ========================================================
    # Sort strongest matches first
    # ========================================================

    matches.sort(
        key=lambda item: (
            item["similarity_score"],
            item["exact_score"],
            item["ngram_score"],
            item["tfidf_score"],
            item["semantic_score"],
        ),
        reverse=True,
    )
    return matches