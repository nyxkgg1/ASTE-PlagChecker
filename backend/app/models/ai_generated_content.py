
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIGeneratedContent(Base):
    """
    Stores AI-generated passages used as a reference corpus.

    Original text and source metadata are kept independently
    from their model-specific embeddings.
    """

    __tablename__ = "ai_generated_content"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    generated_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    normalized_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source_model: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    source_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    generation_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_ai_generated_content_hash",
            "content_hash",
        ),
    )


class AIGeneratedContentEmbedding(Base):
    """
    Stores model-specific vector embeddings for corpus passages.
    """

    __tablename__ = "ai_generated_content_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "ai_generated_content.id",
            name="fk_ai_content_embeddings_content",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "model_registry.id",
            name="fk_ai_content_embeddings_model",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    embedding = mapped_column(
        Vector(1024),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "content_id",
            "model_id",
            name="uq_ai_content_embedding_model",
        ),
        Index(
            "ix_ai_content_embeddings_model_id",
            "model_id",
        ),
    )
