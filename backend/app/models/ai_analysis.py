from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIAnalysisRun(Base):
    __tablename__ = "ai_analysis_runs"

    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'PROCESSING',
                'COMPLETED',
                'PARTIAL_COMPLETED',
                'FAILED',
                'NOT_CONFIGURED'
            )
            """,
            name="ck_ai_analysis_runs_status",
        ),
        Index(
            "idx_ai_analysis_runs_scan_created",
            "scan_id",
            "created_at",
        ),
        Index(
            "idx_ai_analysis_runs_status",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE", name="fk_ai_analysis_runs_scan"),
        nullable=False,
    )

    initiated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_ai_analysis_runs_initiated_by"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PROCESSING",
        server_default="PROCESSING",
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

    scan: Mapped["Scan"] = relationship()

    detector_results: Mapped[list["AIDetectorResult"]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AIDetectorResult(Base):
    __tablename__ = "ai_detector_results"

    __table_args__ = (
        CheckConstraint(
            """
            detector_type IN (
                'CLASSIFIER',
                'CORPUS_MATCH',
                'LINGUISTIC_HEURISTIC',
                'QWEN_EXPERIMENTAL'
            )
            """,
            name="ck_ai_detector_results_type",
        ),
        CheckConstraint(
            """
            status IN (
                'PROCESSING',
                'COMPLETED',
                'FAILED',
                'NOT_CONFIGURED',
                'NOT_ANALYZED'
            )
            """,
            name="ck_ai_detector_results_status",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_ai_detector_results_score_range",
        ),
        CheckConstraint(
            """
            confidence IS NULL
            OR (confidence >= 0 AND confidence <= 1)
            """,
            name="ck_ai_detector_results_confidence_range",
        ),
        UniqueConstraint(
            "run_id",
            "detector_type",
            name="uq_ai_detector_result_run_type",
        ),
        Index(
            "idx_ai_detector_results_run",
            "run_id",
        ),
        Index(
            "idx_ai_detector_results_type_status",
            "detector_type",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_analysis_runs.id", ondelete="CASCADE", name="fk_ai_detector_results_run"),
        nullable=False,
    )

    detector_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    detector_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_registry.id", ondelete="SET NULL", name="fk_ai_detector_results_model"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PROCESSING",
        server_default="PROCESSING",
    )

    score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    score_semantics: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
    )

    metrics: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    analysis_run: Mapped["AIAnalysisRun"] = relationship(
        back_populates="detector_results",
    )

    evidence: Mapped[list["AIDetectorEvidence"]] = relationship(
        back_populates="detector_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AIDetectorEvidence(Base):
    __tablename__ = "ai_detector_evidence"

    __table_args__ = (
        CheckConstraint(
            """
            evidence_score IS NULL
            OR (evidence_score >= 0 AND evidence_score <= 100)
            """,
            name="ck_ai_detector_evidence_score_range",
        ),
        Index(
            "idx_ai_detector_evidence_result",
            "detector_result_id",
        ),
        Index(
            "idx_ai_detector_evidence_sentence",
            "sentence_id",
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
            name="fk_ai_detector_evidence_result",
        ),
        nullable=False,
    )

    sentence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "scan_sentences.id",
            ondelete="CASCADE",
            name="fk_ai_detector_evidence_sentence",
        ),
        nullable=False,
    )

    evidence_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    evidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    detector_result: Mapped["AIDetectorResult"] = relationship(
        back_populates="evidence",
    )

    sentence: Mapped["ScanSentence"] = relationship()
