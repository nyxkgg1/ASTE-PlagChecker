from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.model_registry import ModelRegistry
from app.models.system_setting import SystemSetting


PLAGIARISM_MODEL_SETTING_KEY = "plagiarism_embedding_model"
DEFAULT_PLAGIARISM_MODEL_NAME = "Qwen3-0.6B-Base"


@dataclass(frozen=True)
class LocalEmbeddingModel:
    name: str
    path: Path
    embedding_dimension: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "embedding_dimension": self.embedding_dimension,
        }


def _models_directory() -> Path:
    return Path(settings.model_dir).expanduser().resolve()


def list_local_embedding_models() -> list[LocalEmbeddingModel]:
    models_directory = _models_directory()
    if not models_directory.is_dir():
        return []

    models: list[LocalEmbeddingModel] = []
    for model_path in sorted(models_directory.iterdir()):
        if model_path.is_symlink() or not model_path.is_dir():
            continue

        modules_path = model_path / "modules.json"
        config_path = model_path / "config.json"
        if not modules_path.is_file() or not config_path.is_file():
            continue

        try:
            modules = json.loads(modules_path.read_text(encoding="utf-8"))
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        if not isinstance(modules, list) or not isinstance(config, dict):
            continue
        pooling_module = next(
            (
                module
                for module in modules
                if isinstance(module, dict)
                and str(module.get("type", "")).endswith(".Pooling")
            ),
            None,
        )
        if pooling_module is None:
            continue

        dimension = None
        pooling_path = pooling_module.get("path")
        if isinstance(pooling_path, str) and pooling_path:
            pooling_config_path = (
                model_path / pooling_path / "config.json"
            ).resolve()
            if not pooling_config_path.is_relative_to(model_path.resolve()):
                continue
            try:
                pooling_config = json.loads(
                    pooling_config_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(pooling_config, dict):
                continue
            dimension = pooling_config.get("word_embedding_dimension")
        else:
            dimension = config.get("hidden_size")
        if (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension <= 0
            or dimension > settings.embedding_dimension
        ):
            continue

        models.append(
            LocalEmbeddingModel(
                name=model_path.name,
                path=model_path.resolve(),
                embedding_dimension=dimension,
            )
        )

    return models


def get_local_embedding_model(name: str) -> LocalEmbeddingModel | None:
    return next(
        (
            model
            for model in list_local_embedding_models()
            if model.name == name
        ),
        None,
    )


def get_selected_model_name(db: Session) -> str:
    setting = db.get(SystemSetting, PLAGIARISM_MODEL_SETTING_KEY)
    if setting is not None and setting.value:
        return setting.value
    return DEFAULT_PLAGIARISM_MODEL_NAME


def get_selected_embedding_model(
    db: Session,
) -> tuple[ModelRegistry, LocalEmbeddingModel]:
    model_name = get_selected_model_name(db)
    local_model = get_local_embedding_model(model_name)
    if local_model is None:
        raise RuntimeError(
            f"Selected plagiarism model '{model_name}' is not a compatible "
            "local embedding model."
        )

    registered_model = (
        db.query(ModelRegistry)
        .filter(
            ModelRegistry.model_name == model_name,
            ModelRegistry.model_type == "EMBEDDING",
        )
        .order_by(ModelRegistry.created_at)
        .first()
    )
    if registered_model is None:
        raise RuntimeError(
            f"Selected plagiarism model '{model_name}' is not registered."
        )
    return registered_model, local_model
