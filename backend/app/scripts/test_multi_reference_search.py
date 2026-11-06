from app.db.database import SessionLocal
from app.services.plagiarism_search_service import search_plagiarism_candidates


SCAN_ID = "bfd464e0-a5c1-4d82-90db-b7c5afe4cf30"


def main():
    db = SessionLocal()

    try:
        print("\n========== MULTI-REFERENCE SEARCH TEST ==========\n")

        matches = search_plagiarism_candidates(
            db=db,
            scan_id=SCAN_ID,
        )

        print(f"Total matches returned: {len(matches)}\n")

        for index, match in enumerate(matches, start=1):

            print("=" * 80)
            print(f"MATCH {index}")
            print("=" * 80)

            print("\nRAW MATCH OBJECT:")
            print(match)

            print("\n")

        print("=" * 80)
        print("END OF TEST")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()