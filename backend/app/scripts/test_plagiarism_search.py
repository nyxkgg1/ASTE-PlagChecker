from app.db.database import SessionLocal
from app.models.scan import Scan
from app.services.plagiarism_search_service import (
    search_plagiarism_candidates,
)


def main():

    db = SessionLocal()

    try:

        scan = (
            db.query(Scan)
            .order_by(Scan.created_at.desc())
            .first()
        )

        if not scan:
            print("No scans found.")
            return

        print(f"Testing scan: {scan.id}")
        print(f"Title: {scan.title}")

        matches = search_plagiarism_candidates(
            db,
            scan.id,
        )

        print(
            f"Potential plagiarism matches: {len(matches)}"
        )

        for index, match in enumerate(
            matches[:10],
            start=1,
        ):

            scan_sentence = match["scan_sentence"]
            reference_sentence = match[
                "reference_sentence"
            ]

            score = match["similarity_score"]

            print()
            print(f"Match #{index}")
            print(f"Exact:  {match['exact_score']:.4f}")
            print(f"N-gram: {match['ngram_score']:.4f}")
            print(f"TF-IDF: {match['tfidf_score']:.4f}")
            print(f"Final:  {match['similarity_score']:.4f}")


            print(
                "SCAN:",
                scan_sentence.raw_text[:200],
            )

            print(
                "REFERENCE:",
                reference_sentence.raw_text[:200],
            )

    finally:

        db.close()


if __name__ == "__main__":
    main()