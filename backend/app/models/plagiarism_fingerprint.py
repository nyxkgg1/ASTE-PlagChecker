import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReferenceSentenceFingerprint(Base):
    __tablename__ = "reference_sentence_fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    reference_sentence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "reference_sentences.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    fingerprint_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="WORD",
        server_default="WORD",
    )

    ngram_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    fingerprint_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    reference_sentence = relationship(
        "ReferenceSentence",
        back_populates="fingerprints",
    )

    __table_args__ = (
        UniqueConstraint(
            "reference_sentence_id",
            "fingerprint_type",
            "ngram_size",
            "fingerprint_hash",
            name="uq_reference_sentence_fingerprint",
        ),
        Index(
            "ix_reference_sentence_fingerprint_hash",
            "fingerprint_hash",
        ),
        Index(
            "ix_reference_sentence_fingerprint_sentence",
            "reference_sentence_id",
        ),
    )