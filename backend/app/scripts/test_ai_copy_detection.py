from __future__ import annotations

import sys

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.services.ai_detection_persistence_service import (
    save_ai_detection_analysis,
)


def main():

    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "python -m app.scripts.test_ai_copy_detection "
            "SCAN_UUID"
        )
        return

    scan_id = sys.argv[1]

    user_id = (
        "a038b001-4410-4506-a9c3-2238ef394bce"
    )

    db: Session = SessionLocal()

    try:

        print("=" * 70)
        print("AI GENERATED-CORPUS DETECTION TEST")
        print("=" * 70)

        print(f"Scan ID : {scan_id}")
        print("Source  : DUMMY_LLAMA")

        result = save_ai_detection_analysis(
            db=db,
            scan_id=scan_id,
            initiated_by=user_id,
        )

        db.commit()
        db.refresh(result)

        print()
        print("RESULT")
        print("-" * 70)

        print(
            f"Result ID      : {result.id}"
        )

        print(
            f"Status         : {result.status}"
        )

        print(
            f"AI Copy Score  : "
            f"{result.ai_probability:.4f}"
        )

        print(
            f"Confidence     : "
            f"{result.confidence:.4f}"
        )

        print(
            f"Algorithm      : "
            f"{result.algorithm_version}"
        )

        signals = (
            result.detected_signals
            or {}
        )

        document = (
            signals.get("document", {})
        )

        print()
        print("DOCUMENT")
        print("-" * 70)

        for key, value in document.items():
            print(
                f"{key:35} : {value}"
            )

        matches = (
            signals.get("matches", [])
        )

        print()
        print(
            f"TOP MATCHES ({len(matches)})"
        )
        print("-" * 70)

        for index, match in enumerate(
            matches[:10],
            start=1,
        ):

            print(
                f"\nMatch #{index}"
            )

            print(
                f"Source ID       : "
                f"{match.get('source_id')}"
            )

            print(
                f"Method          : "
                f"{match.get('match_method')}"
            )

            print(
                f"Match score     : "
                f"{match.get('match_score'):.4f}"
            )

            print(
                f"Exact           : "
                f"{match.get('exact_score'):.4f}"
            )

            print(
                f"N-gram          : "
                f"{match.get('ngram_score'):.4f}"
            )

            print(
                f"TF-IDF          : "
                f"{match.get('tfidf_score'):.4f}"
            )

            print(
                f"Semantic        : "
                f"{match.get('semantic_score'):.4f}"
            )

            print(
                f"AI source text  : "
                f"{match.get('source_text')}"
            )

        print()
        print("=" * 70)
        print(
            "PASS: AI CORPUS DETECTION COMPLETED"
        )
        print("=" * 70)

    except Exception as exc:

        db.rollback()

        print()
        print("=" * 70)
        print("FAIL: AI CORPUS DETECTION")
        print("=" * 70)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()