from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIDetectorExplanation(Base):
    """
    Stores supplementary LLM-generated explanations for detector results.

    These explanations never replace or modify the original detector
    scores, metrics, evidence, or deterministic explanations.
    """

    __tablename__ = "ai_detector_explanations"

    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'PROCESSING',
                'COMPLETED',
                'FAILED'
            )
            """,
            name="ck_ai_detector_explanations_status",
        ),
        Index(
            "ix_ai_detector_explanations_result",
            "detector_result_id",
        ),
        Index(
            "ix_ai_detector_explanations_status",
            "status",
        ),
        Index(
            "ix_ai_detector_explanations_created",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    detector_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "ai_detector_results.id",
            ondelete="CASCADE",
            name="fk_ai_detector_explanations_detector_result",
        ),
        nullable=False,
    )

    model_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    prompt_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PROCESSING",
        server_default="PROCESSING",
    )

    explanation_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    generation_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    detector_result = relationship("AIDetectorResult")
