from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sentence_transformers import SentenceTransformer

from app.core.config import settings


@lru_cache(maxsize=1)
def _load_embedding_model(model_path: str) -> SentenceTransformer:
    return SentenceTransformer(
        model_path,
        local_files_only=True,
    )


def get_embedding_model(
    model_path: str | Path | None = None,
) -> SentenceTransformer:
    """
    Load the selected local embedding model once and keep it in memory.
    No internet access is required.
    """
    path = Path(model_path or settings.embedding_model_path).expanduser().resolve()
    return _load_embedding_model(str(path))


def _fit_embedding_dimension(embedding: list[float]) -> list[float]:
    expected_dimension = settings.embedding_dimension
    if len(embedding) > expected_dimension:
        raise ValueError(
            f"Embedding dimension {len(embedding)} exceeds the database "
            f"dimension {expected_dimension}."
        )
    return embedding + [0.0] * (expected_dimension - len(embedding))


def generate_embedding(
    text: str,
    model_path: str | Path | None = None,
) -> list[float]:
    """
    Generate a single normalized embedding.
    Expected dimension: 1024.
    """
    if not text or not text.strip():
        return []

    model = get_embedding_model(model_path)

    embedding = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return _fit_embedding_dimension(embedding.tolist())


def generate_embeddings(
    texts: list[str],
    batch_size: int = 32,
    model_path: str | Path | None = None,
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts efficiently.
    """
    if not texts:
        return []

    model = get_embedding_model(model_path)

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=False,
    )

    return [
        _fit_embedding_dimension(embedding)
        for embedding in embeddings.tolist()
    ]