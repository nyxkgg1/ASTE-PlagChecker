from __future__ import annotations

import uuid
from pathlib import Path

from app.db.database import SessionLocal
from app.models.scan import Scan, ScanPage, ScanSentence
from app.models.plagiarism import PlagiarismAnalysis, PlagiarismMatch
from app.models.user import User
from app.services.plagiarism_persistence_service import (
    save_plagiarism_analysis,
)


def main():

    db = SessionLocal()

    try:

        print()
        print("=" * 90)
        print("DATABASE-BACKED PLAGIARISM TEST")
        print("=" * 90)

        # ====================================================
        # 1. Get admin/test user
        # ====================================================

        user = (
            db.query(User)
            .filter(
                User.id
                == uuid.UUID(
                    "a038b001-4410-4506-a9c3-2238ef394bce"
                )
            )
            .first()
        )

        if not user:

            print()
            print(
                "ERROR: Test user was not found."
            )

            return

        print()
        print("Test user:")
        print(user.id)

        # ====================================================
        # 2. Create Scan
        # ====================================================

        scan = Scan(
            title="DB Plagiarism Integration Test",
            file_name="test_plagiarism.txt",
            file_path="uploads/scans/test_plagiarism.txt",
            file_size=0,
            mime_type="text/plain",
            sha256_hash="test-plagiarism-integration",
            scanned_by=user.id,
            owner_id=user.id,
            status="UPLOADED",
        )

        db.add(scan)
        db.flush()

        print()
        print("Created scan:")
        print(scan.id)

        # ====================================================
        # 3. Create scan page
        # ====================================================

        page = ScanPage(
            scan_id=scan.id,
            page_number=1,
            raw_text=(
                "The aircraft was evaluated under "
                "standard atmospheric conditions.\n\n"
                "The aircraft evaluation was conducted "
                "under normal atmospheric conditions.\n\n"
                "The maintenance team repaired the "
                "landing gear after replacing a damaged wheel."
            ),
        )

        db.add(page)
        db.flush()

        # ====================================================
        # 4. Create test sentences
        # ====================================================

        sentences = [

            (
                "The aircraft was evaluated under "
                "standard atmospheric conditions."
            ),

            (
                "The aircraft evaluation was conducted "
                "under normal atmospheric conditions."
            ),

            (
                "The maintenance team repaired the "
                "landing gear after replacing a damaged wheel."
            ),

        ]

        for index, text in enumerate(
            sentences,
            start=1,
        ):

            normalized = " ".join(
                text.lower().split()
            )

            sentence = ScanSentence(
                scan_id=scan.id,
                page_id=page.id,
                sentence_index=index,
                raw_text=text,
                normalized_text=normalized,
                token_count=len(
                    normalized.split()
                ),
            )

            db.add(sentence)

        db.flush()

        print()
        print(
            f"Created {len(sentences)} scan sentences."
        )

        # ====================================================
        # 5. Commit scan data
        # ====================================================

        db.commit()

        print()
        print("Scan data committed.")

        # ====================================================
        # 6. Run plagiarism analysis
        # ====================================================

        print()
        print("-" * 90)
        print("RUNNING PLAGIARISM ANALYSIS")
        print("-" * 90)

        analysis = save_plagiarism_analysis(
            db=db,
            scan_id=scan.id,
            initiated_by=user.id,
        )

        db.commit()

        # ====================================================
        # 7. Display analysis
        # ====================================================

        print()
        print("=" * 90)
        print("PLAGIARISM ANALYSIS RESULT")
        print("=" * 90)

        print()
        print("Analysis ID:")
        print(analysis.id)

        print()
        print("Scan ID:")
        print(analysis.scan_id)

        print()
        print("Status:")
        print(analysis.status)

        print()
        print(
            "Algorithm version:",
            analysis.algorithm_version,
        )

        print()
        print(
            "Overall similarity:",
            round(
                float(
                    analysis.overall_similarity or 0.0
                ),
                4,
            ),
        )

        print()
        print(
            "Exact match score:",
            round(
                float(
                    analysis.exact_match_score or 0.0
                ),
                4,
            ),
        )

        print()
        print(
            "N-gram score:",
            round(
                float(
                    analysis.ngram_score or 0.0
                ),
                4,
            ),
        )

        print()
        print(
            "TF-IDF score:",
            round(
                float(
                    analysis.tfidf_score or 0.0
                ),
                4,
            ),
        )

        print()
        print(
            "Semantic score:",
            round(
                float(
                    analysis.semantic_score or 0.0
                ),
                4,
            ),
        )

        print()
        print(
            "Cross encoder score:",
            analysis.cross_encoder_score,
        )

        print()
        print(
            "Completed at:",
            analysis.completed_at,
        )

        # ====================================================
        # 8. Retrieve saved matches
        # ====================================================

        matches = (
            db.query(PlagiarismMatch)
            .filter(
                PlagiarismMatch.analysis_id
                == analysis.id
            )
            .order_by(
                PlagiarismMatch.similarity_score.desc()
            )
            .all()
        )

        print()
        print("=" * 90)
        print("SAVED PLAGIARISM MATCHES")
        print("=" * 90)

        print()
        print(
            "Number of matches:",
            len(matches),
        )

        for index, match in enumerate(
            matches,
            start=1,
        ):

            print()
            print("-" * 90)
            print(
                f"MATCH #{index}"
            )
            print("-" * 90)

            print()
            print(
                "Match ID:",
                match.id,
            )

            print(
                "Detection method:",
                match.detection_method,
            )

            print(
                "Similarity:",
                round(
                    float(
                        match.similarity_score
                    ),
                    4,
                ),
            )

            print()
            print("Scan text:")
            print(match.scan_text)

            print()
            print("Reference text:")
            print(match.reference_text)

            print()
            print(
                "Scan page:",
                match.scan_page_number,
            )

            print(
                "Reference page:",
                match.reference_page_number,
            )

        # ====================================================
        # 9. Final validation
        # ====================================================

        print()
        print("=" * 90)
        print("VALIDATION")
        print("=" * 90)

        if analysis.status == "COMPLETED":

            print(
                "PASS: Analysis completed successfully."
            )

        else:

            print(
                "FAIL: Analysis did not complete."
            )

        if len(matches) >= 1:

            print(
                "PASS: Plagiarism matches were persisted."
            )

        else:

            print(
                "WARNING: No plagiarism matches were persisted."
            )

        # ====================================================
        # 10. Cleanup
        # ====================================================

        print()
        print(
            "Test scan ID for database inspection:",
            scan.id,
        )

        print()
        print(
            "The test data has NOT been deleted."
        )

        print(
            "This allows us to inspect the PostgreSQL records."
        )

        print()
        print("=" * 90)

    except Exception as exc:

        db.rollback()

        print()
        print("=" * 90)
        print("TEST FAILED")
        print("=" * 90)

        print()
        print(
            type(exc).__name__,
            ":",
            str(exc),
        )

        raise

    finally:

        db.close()


if __name__ == "__main__":
    main()
