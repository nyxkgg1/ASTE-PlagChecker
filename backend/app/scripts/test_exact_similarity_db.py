
from app.db.database import SessionLocal
from app.models.reference import ReferenceDocument, ReferenceSentence
from app.models.scan import ScanSentence
from app.services.plagiarism_fingerprint_service import (
    normalize_for_matching,
    exact_text_similarity,
)
import inspect

SCAN_ID = "d4b8bca5-b259-4ab0-8161-da9fbb52738b"

db = SessionLocal()

try:
    print("Imported function file:", inspect.getfile(exact_text_similarity))

    scan = (
        db.query(ScanSentence)
        .filter(
            ScanSentence.scan_id == SCAN_ID,
            ScanSentence.sentence_index == 2,
        )
        .first()
    )

    print("\nActual scan text:", repr(scan.normalized_text))
    print("Normalized scan:", repr(normalize_for_matching(scan.normalized_text)))

    references = (
        db.query(ReferenceSentence, ReferenceDocument)
        .join(
            ReferenceDocument,
            ReferenceDocument.id == ReferenceSentence.reference_document_id,
        )
        .filter(
            ReferenceDocument.title.in_([
                "Ref 2",
                "Test FTER Reference Document",
            ]),
            ReferenceSentence.normalized_text.ilike(
                "%flight test team conducted the trial%"
            ),
        )
        .all()
    )

    for reference, document in references:
        print("\nDocument:", document.title)
        print("Actual reference:", repr(reference.normalized_text))
        print(
            "Normalized reference:",
            repr(normalize_for_matching(reference.normalized_text)),
        )
        print(
            "Exact similarity:",
            exact_text_similarity(
                scan.normalized_text,
                reference.normalized_text,
            ),
        )

finally:
    db.close()
