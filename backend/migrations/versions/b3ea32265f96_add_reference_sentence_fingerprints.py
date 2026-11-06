"""add reference sentence fingerprints

Revision ID: b3ea32265f96
Revises: baseline_fter_001
Create Date: 2026-10-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b3ea32265f96"

down_revision: Union[str, Sequence[str], None] = "baseline_fter_001"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create reference sentence fingerprint table."""

    op.create_table(
        "reference_sentence_fingerprints",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "reference_sentence_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "ngram_size",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "fingerprint_hash",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["reference_sentence_id"],
            ["reference_sentences.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "reference_sentence_id",
            "ngram_size",
            "fingerprint_hash",
            name="uq_reference_sentence_fingerprint",
        ),
    )

    op.create_index(
        "ix_reference_sentence_fingerprint_hash",
        "reference_sentence_fingerprints",
        ["fingerprint_hash"],
        unique=False,
    )

    op.create_index(
        "ix_reference_sentence_fingerprint_sentence",
        "reference_sentence_fingerprints",
        ["reference_sentence_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove reference sentence fingerprint table."""

    op.drop_index(
        "ix_reference_sentence_fingerprint_sentence",
        table_name="reference_sentence_fingerprints",
    )

    op.drop_index(
        "ix_reference_sentence_fingerprint_hash",
        table_name="reference_sentence_fingerprints",
    )

    op.drop_table(
        "reference_sentence_fingerprints",
    )