from __future__ import annotations

from pathlib import Path

from app.db.database import SessionLocal
from app.models.model_registry import ModelRegistry
from app.services.ai_authorship_classifier_service import (
    CLASSIFIER_MODEL_NAME,
    CLASSIFIER_MODEL_VERSION,
)


MODEL_DIRECTORY = (
    Path(__file__).resolve().parents[3]
    / "models"
    / "ai-text-detector-modernbert"
)

MODEL_FILES = [
    "LICENSE",
    "config.json",
    "detector-config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
]


def main() -> None:
    missing_files = [
        filename
        for filename in MODEL_FILES
        if not (MODEL_DIRECTORY / filename).is_file()
    ]
    if missing_files:
        raise FileNotFoundError(
            f"Local classifier files are missing from {MODEL_DIRECTORY}: "
            + ", ".join(missing_files)
        )

    model_path = MODEL_DIRECTORY.resolve()
    db = SessionLocal()
    try:
        registered_models = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == CLASSIFIER_MODEL_NAME,
                ModelRegistry.version == CLASSIFIER_MODEL_VERSION,
                ModelRegistry.model_type == "CLASSIFIER",
            )
            .all()
        )

        if len(registered_models) > 1:
            raise RuntimeError(
                "Multiple registry rows already exist for this classifier; "
                "resolve duplicates before registering it."
            )

        if registered_models:
            model = registered_models[0]
            model.local_path = str(model_path.resolve())
            model.is_active = True
            model.model_hash = CLASSIFIER_MODEL_VERSION
        else:
            db.add(
                ModelRegistry(
                    model_name=CLASSIFIER_MODEL_NAME,
                    model_type="CLASSIFIER",
                    version=CLASSIFIER_MODEL_VERSION,
                    local_path=str(model_path.resolve()),
                    model_hash=CLASSIFIER_MODEL_VERSION,
                    is_active=True,
                )
            )

        db.commit()
        print(f"AI-authorship classifier installed at: {model_path.resolve()}")
        print(f"Registered model: {CLASSIFIER_MODEL_NAME}")
        print(f"Revision: {CLASSIFIER_MODEL_VERSION}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
