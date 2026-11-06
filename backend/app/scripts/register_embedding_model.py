from pathlib import Path

from app.db.database import SessionLocal
from app.models.model_registry import ModelRegistry


MODEL_NAME = "Qwen3-0.6B-Base"
MODEL_TYPE = "EMBEDDING"
MODEL_VERSION = "0.6B-Base"

MODEL_PATH = str(
    Path(__file__).resolve().parents[3]
    / "models"
    / "Qwen3-0.6B-Base"
)


def main():
    db = SessionLocal()

    try:
        existing = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == MODEL_NAME,
                ModelRegistry.version == MODEL_VERSION,
            )
            .first()
        )

        if existing:
            existing.local_path = MODEL_PATH
            existing.is_active = True

            db.commit()

            print("Embedding model already registered.")
            print("Model ID:", existing.id)
            print("Path:", existing.local_path)

            return

        model = ModelRegistry(
            model_name=MODEL_NAME,
            model_type=MODEL_TYPE,
            version=MODEL_VERSION,
            local_path=MODEL_PATH,
            model_hash=None,
            is_active=True,
        )

        db.add(model)
        db.commit()
        db.refresh(model)

        print("Embedding model registered successfully.")
        print("Model ID:", model.id)
        print("Model:", model.model_name)
        print("Version:", model.version)
        print("Path:", model.local_path)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()