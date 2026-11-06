from sqlalchemy import func
from app.db.database import SessionLocal
from app.models.reference import ReferenceDocument, ReferenceSentence
from app.models.plagiarism_fingerprint import (
    ReferenceSentenceFingerprint,
)
from app.services.reference_fingerprint_service import (
    index_reference_sentence,
)


def main():
    db = SessionLocal()

    try:
        sentence = (
            db.query(ReferenceSentence)
            .join(
                ReferenceDocument,
                ReferenceDocument.id
                == ReferenceSentence.reference_document_id,
            )
            .filter(
                ReferenceDocument.status == "ACTIVE"
            )
            .first()
        )

        if not sentence:
            print(
                "NO ACTIVE REFERENCE SENTENCE FOUND."
            )
            print(
                "Add and index at least one ACTIVE "
                "reference document first."
            )
            return

        print("Reference sentence:")
        print(sentence.raw_text)

        fingerprint_count = index_reference_sentence(
            db,
            sentence,
        )

        db.commit()

        print(
            f"\nFingerprints created: "
            f"{fingerprint_count}"
        )

        fingerprints = (
            db.query(
                ReferenceSentenceFingerprint
            )
            .filter(
                ReferenceSentenceFingerprint
                .reference_sentence_id
                == sentence.id
            )
            .order_by(
                ReferenceSentenceFingerprint.ngram_size,
                ReferenceSentenceFingerprint.fingerprint_hash,
            )
            .all()
        )

        print(
            f"Fingerprints stored in DB: "
            f"{len(fingerprints)}"
        )

        for fingerprint in fingerprints[:10]:
            print(
                f"n={fingerprint.ngram_size} | "
                f"{fingerprint.fingerprint_hash}"
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()