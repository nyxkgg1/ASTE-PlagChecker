from sqlalchemy.orm import Session

from app.models.reference import ReferenceDocument, ReferenceSentence
from app.models.plagiarism_fingerprint import (
    ReferenceSentenceFingerprint,
)
from app.services.plagiarism_fingerprint_service import (
    generate_ngram_fingerprints,
    generate_character_ngram_fingerprints,
)


DEFAULT_NGRAM_SIZES = (3, 5)


def index_reference_sentence(
    db: Session,
    sentence: ReferenceSentence,
) -> int:
    """
    Generate and persist fingerprints for one reference sentence.
    """

    # Replace only the fingerprint types managed by this service.
    # Preserve any other fingerprint types that may be added later.
    db.query(ReferenceSentenceFingerprint).filter(
        ReferenceSentenceFingerprint.reference_sentence_id == sentence.id,
        ReferenceSentenceFingerprint.fingerprint_type.in_(
            ["WORD", "CHARACTER"]
        ),
    ).delete(synchronize_session=False)

    created_count = 0

    # Word-level fingerprints: preserve existing retrieval behavior.
    for ngram_size in DEFAULT_NGRAM_SIZES:
        fingerprints = generate_ngram_fingerprints(
            sentence.normalized_text,
            n=ngram_size,
        )

        for fingerprint in fingerprints:
            db.add(
                ReferenceSentenceFingerprint(
                    reference_sentence_id=sentence.id,
                    fingerprint_type="WORD",
                    ngram_size=ngram_size,
                    fingerprint_hash=fingerprint,
                )
            )
            created_count += 1

    # Character-level fingerprints: additional candidate-retrieval signal.
    character_fingerprints = generate_character_ngram_fingerprints(
        sentence.normalized_text,
        n=4,
    )

    for fingerprint in character_fingerprints:
        db.add(
            ReferenceSentenceFingerprint(
                reference_sentence_id=sentence.id,
                fingerprint_type="CHARACTER",
                ngram_size=4,
                fingerprint_hash=fingerprint,
            )
        )
        created_count += 1

    return created_count


def index_reference_document_fingerprints(
    db: Session,
    reference_document_id,
) -> int:
    """
    Generate fingerprints for all sentences belonging
    to the current version of an active reference document.
    """

    reference_document = (
        db.query(ReferenceDocument)
        .filter(
            ReferenceDocument.id == reference_document_id,
            ReferenceDocument.status == "ACTIVE",
        )
        .first()
    )

    if not reference_document:
        raise ValueError(
            "Active reference document was not found."
        )

    sentences = (
        db.query(ReferenceSentence)
        .filter(
            ReferenceSentence.reference_document_id
            == reference_document.id
        )
        .all()
    )

    total_fingerprints = 0

    for sentence in sentences:
        total_fingerprints += index_reference_sentence(
            db,
            sentence,
        )

    db.commit()

    return total_fingerprints