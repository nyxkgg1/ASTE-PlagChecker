from app.db.database import SessionLocal
from app.models.model_registry import ModelRegistry
from app.models.reference import ReferenceSentence
from app.services.reference_embedding_service import (
    create_reference_sentence_embeddings,
)


MODEL_NAME = "Qwen3-0.6B-Base"
MODEL_VERSION = "0.6B-Base"

BATCH_SIZE = 32


def main():
    db = SessionLocal()

    try:
        print("Looking for active embedding model...")

        model = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == MODEL_NAME,
                ModelRegistry.version == MODEL_VERSION,
                ModelRegistry.is_active.is_(True),
            )
            .first()
        )

        if not model:
            raise RuntimeError(
                "Qwen3 embedding model is not registered."
            )

        print("Model:", model.model_name)
        print("Version:", model.version)
        print("Model ID:", model.id)
        print("Path:", model.local_path)

        sentences = (
            db.query(ReferenceSentence)
            .order_by(ReferenceSentence.id)
            .all()
        )

        print("Reference sentences:", len(sentences))

        if not sentences:
            print(
                "\nNo reference sentences found."
            )
            print(
                "First index at least one reference document."
            )
            return

        print("\nGenerating embeddings...")
        print("Batch size:", BATCH_SIZE)

        count = create_reference_sentence_embeddings(
            db=db,
            sentences=sentences,
            model_id=model.id,
            batch_size=BATCH_SIZE,
        )

        print()
        print("===================================")
        print("Embedding indexing completed")
        print("===================================")
        print("Embeddings created/updated:", count)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()