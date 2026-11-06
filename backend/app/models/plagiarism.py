import uuid
from datetime import datetime
from sqlalchemy import Numeric
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.scan import Scan
from app.db.base import Base


class PlagiarismAnalysis(Base):
    __tablename__ = "plagiarism_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
    )

    initiated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PROCESSING",
    )

    overall_similarity: Mapped[float | None] = mapped_column(
    Numeric(10, 8),
    nullable=True,
)

    exact_match_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    ngram_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    tfidf_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    semantic_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    cross_encoder_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    algorithm_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    scan: Mapped["Scan"] = relationship(
        "Scan",
        back_populates="plagiarism_analyses",
    )

    matches: Mapped[list["PlagiarismMatch"]] = relationship(
        "PlagiarismMatch",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class PlagiarismMatch(Base):
    __tablename__ = "plagiarism_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "plagiarism_analyses.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    reference_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "reference_documents.id"
        ),
        nullable=False,
    )

    scan_sentence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "scan_sentences.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    reference_sentence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "reference_sentences.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    detection_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    similarity_score: Mapped[float] = mapped_column(
        nullable=False,
    )

    scan_page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    reference_page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    scan_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reference_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    # Plagiarism analysis that produced this match
    analysis: Mapped["PlagiarismAnalysis"] = relationship(
        "PlagiarismAnalysis",
        back_populates="matches",
    )

    # Reference sentence that matched the scan sentence
    reference_sentence: Mapped["ReferenceSentence"] = relationship(
        "ReferenceSentence",
        foreign_keys=[reference_sentence_id],
    )

    # Scan sentence that was matched
    scan_sentence: Mapped["ScanSentence"] = relationship(
        "ScanSentence",
        foreign_keys=[scan_sentence_id],
    )

class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    request_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    reference_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference_documents.id"),
        nullable=True,
    )

    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    admin_comments: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )