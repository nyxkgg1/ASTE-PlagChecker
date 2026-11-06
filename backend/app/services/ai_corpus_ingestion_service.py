
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_generated_content import (
    AIGeneratedContent,
    AIGeneratedContentEmbedding,
)
from app.models.model_registry import ModelRegistry
from app.services.embedding_service import generate_embedding


EMBEDDING_MODEL_NAME = "Qwen3-0.6B-Base"
EMBEDDING_MODEL_VERSION = "0.6B-Base"


def normalize_corpus_text(text: str) -> str:
    """Normalize whitespace and Unicode for consistent matching."""

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Generated text cannot be empty.")

    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def calculate_content_hash(normalized_text: str) -> str:
    """Return a SHA-256 hash of normalized text."""

    return hashlib.sha256(
        normalized_text.encode("utf-8")
    ).hexdigest()


def get_corpus_embedding_model(db: Session) -> ModelRegistry:
    """Find the active Qwen embedding model in ModelRegistry."""

    models = (
        db.query(ModelRegistry)
        .filter(
            ModelRegistry.model_name == EMBEDDING_MODEL_NAME,
            ModelRegistry.version == EMBEDDING_MODEL_VERSION,
            ModelRegistry.model_type == "EMBEDDING",
            ModelRegistry.is_active.is_(True),
        )
        .all()
    )

    if len(models) != 1:
        raise ValueError(
            "Expected exactly one active Qwen3-0.6B-Base "
            "embedding model in ModelRegistry."
        )

    return models[0]


def ingest_ai_generated_content(
    db: Session,
    generated_text: str,
    source_model: str | None = None,
    source_version: str | None = None,
    generation_date: datetime | None = None,
    metadata: dict | None = None,
) -> tuple[AIGeneratedContent, bool, bool]:
    """
    Insert an AI-generated document and its embedding.

    Returns:
        content: Stored corpus document.
        content_created: Whether a new document was inserted.
        embedding_created: Whether a new embedding was inserted.

    The caller owns the transaction and must commit or roll back.
    """

    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary.")

    normalized_text = normalize_corpus_text(generated_text)
    content_hash = calculate_content_hash(normalized_text)

    model = get_corpus_embedding_model(db)

    # Reuse an existing document with identical normalized content.
    content = (
        db.query(AIGeneratedContent)
        .filter(
            AIGeneratedContent.content_hash == content_hash,
            AIGeneratedContent.is_active.is_(True),
        )
        .first()
    )

    content_created = content is None

    if content is None:
        content = AIGeneratedContent(
            generated_text=generated_text,
            normalized_text=normalized_text,
            content_hash=content_hash,
            source_model=source_model,
            source_version=source_version,
            generation_date=generation_date,
            source_metadata=metadata or {},
            is_active=True,
        )

        db.add(content)
        db.flush()

    # Check whether this content already has an embedding
    # for the selected model.
    existing_embedding = (
        db.query(AIGeneratedContentEmbedding)
        .filter(
            AIGeneratedContentEmbedding.content_id == content.id,
            AIGeneratedContentEmbedding.model_id == model.id,
        )
        .first()
    )

    if existing_embedding is not None:
        return content, content_created, False

    embedding_vector = generate_embedding(normalized_text)

    if len(embedding_vector) != settings.embedding_dimension:
        raise ValueError(
            f"Embedding dimension mismatch: expected "
            f"{settings.embedding_dimension}, received "
            f"{len(embedding_vector)}."
        )

    embedding_record = AIGeneratedContentEmbedding(
        content_id=content.id,
        model_id=model.id,
        embedding=embedding_vector,
    )

    db.add(embedding_record)
    db.flush()

    return content, content_created, True
