from app.db.database import SessionLocal
from app.models.reference import ReferenceDocument, ReferenceSentence
from app.models.scan import ScanSentence
from app.services.plagiarism_fingerprint_service import (
    character_similarity,
    exact_text_similarity,
    ngram_similarity,
)
from app.api.routes import scan

SCAN_ID = "d4b8bca5-b259-4ab0-8161-da9fbb52738b"


def main():
    db = SessionLocal()

    try:
        scan_sentences = (
            db.query(ScanSentence)
            .filter(ScanSentence.scan_id == SCAN_ID)
            .order_by(ScanSentence.sentence_index)
            .all()
        )

        if not scan_sentences:
            print("No scan sentences found. Check SCAN_ID.")
            return

        references = (
            db.query(ReferenceSentence, ReferenceDocument)
            .join(
                ReferenceDocument,
                ReferenceDocument.id
                == ReferenceSentence.reference_document_id,
            )
            .filter(ReferenceDocument.status == "ACTIVE")
            .all()
        )

        print(f"Scan sentences: {len(scan_sentences)}")
        print(f"Active reference sentences: {len(references)}")

        for scan in scan_sentences:
            scan_text = scan.normalized_text or ""

            if len(scan_text.strip()) < 20:
                continue

            scored = []

            for reference, document in references:
                reference_text = reference.normalized_text or ""

                if len(reference_text.strip()) < 20:
                    continue

                scored.append(
                    {
                        "character": character_similarity(
                            scan_text, reference_text
                        ),
                        "exact": exact_text_similarity(
                            scan_text, reference_text
                        ),
                        "ngram": ngram_similarity(
                            scan_text, reference_text, n=5
                        ),
                        "document": document.title,
                        "text": reference_text,
                    }
                )

            scored.sort(
                key=lambda item: item["character"],
                reverse=True,
            )

            print("\n" + "=" * 80)
            print(f"Scan sentence index: {scan.sentence_index}")
            print(f"Scan text: {scan_text!r}")

            for rank, result in enumerate(scored[:5], start=1):
                print(f"\nCandidate {rank}")
                print(f"Reference document: {result['document']}")
                print(f"Character similarity: {result['character']:.4f}")
                print(f"Exact similarity:     {result['exact']:.4f}")
                print(f"Word n-gram score:    {result['ngram']:.4f}")
                print(f"Reference text: {result['text']!r}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
