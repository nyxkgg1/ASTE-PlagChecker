from app.db.database import SessionLocal
from app.models.reference import ReferenceDocument, ReferenceSentence
from app.models.plagiarism_fingerprint import ReferenceSentenceFingerprint
from app.services.plagiarism_fingerprint_service import (
    generate_character_ngram_fingerprints,
)

CHARACTER_NGRAM_SIZE = 4
BATCH_SIZE = 100


def main():
    db = SessionLocal()

    try:
        # Only sentences belonging to active reference documents.
        sentences = (
            db.query(ReferenceSentence)
            .join(
                ReferenceDocument,
                ReferenceSentence.reference_document_id
                == ReferenceDocument.id,
            )
            .filter(ReferenceDocument.status == "ACTIVE")
            .all()
        )

        sentence_ids = [sentence.id for sentence in sentences]

        if not sentence_ids:
            print("No sentences found in active reference documents.")
            return

        print(f"Active reference sentences: {len(sentences)}")

        # Replace only CHARACTER fingerprints for these sentences.
        # WORD fingerprints and embeddings remain untouched.
        deleted = (
            db.query(ReferenceSentenceFingerprint)
            .filter(
                ReferenceSentenceFingerprint.reference_sentence_id.in_(
                    sentence_ids
                ),
                ReferenceSentenceFingerprint.fingerprint_type
                == "CHARACTER",
            )
            .delete(synchronize_session=False)
        )

        db.flush()
        print(f"Previous CHARACTER rows replaced: {deleted}")

        inserted = 0

        for index, sentence in enumerate(sentences, start=1):
            fingerprints = generate_character_ngram_fingerprints(
                sentence.normalized_text or "",
                n=CHARACTER_NGRAM_SIZE,
            )

            for fingerprint in fingerprints:
                db.add(
                    ReferenceSentenceFingerprint(
                        reference_sentence_id=sentence.id,
                        fingerprint_type="CHARACTER",
                        ngram_size=CHARACTER_NGRAM_SIZE,
                        fingerprint_hash=fingerprint,
                    )
                )

            inserted += len(fingerprints)

            if index % BATCH_SIZE == 0:
                db.flush()
                print(
                    f"Processed {index}/{len(sentences)} sentences; "
                    f"generated {inserted} character fingerprints."
                )

        db.commit()

        print("\nBackfill completed successfully.")
        print(f"Sentences processed: {len(sentences)}")
        print(f"CHARACTER fingerprints inserted: {inserted}")

        # Verify persisted counts.
        results = (
            db.query(
                ReferenceSentenceFingerprint.fingerprint_type,
                ReferenceSentenceFingerprint.ngram_size,
            )
            .filter(
                ReferenceSentenceFingerprint.reference_sentence_id.in_(
                    sentence_ids
                )
            )
            .all()
        )

        counts = {}
        for fingerprint_type, ngram_size in results:
            key = (fingerprint_type, ngram_size)
            counts[key] = counts.get(key, 0) + 1

        print("\nFingerprint counts for active reference sentences:")
        for key, count in sorted(counts.items()):
            print(
                f"Type={key[0]}, n={key[1]}: {count} rows"
            )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
