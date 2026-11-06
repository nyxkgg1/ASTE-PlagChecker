from app.db.database import SessionLocal
from app.models.reference import ReferenceDocument
from app.services.reference_index_service import (
    index_reference_document,
)


def main():

    db = SessionLocal()

    try:

        reference = (
            db.query(ReferenceDocument)
            .filter(
                ReferenceDocument.status == "ACTIVE"
            )
            .first()
        )

        if not reference:

            print(
                "No ACTIVE reference document found."
            )

            return

        print(
            f"Indexing: {reference.file_name}"
        )

        count = index_reference_document(
            db,
            reference,
        )

        db.commit()

        print(
            f"Indexed {count} sentences."
        )

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


if __name__ == "__main__":
    main()