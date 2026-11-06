"""Add fingerprint type to reference sentence fingerprints."""

from alembic import op
import sqlalchemy as sa

revision = "a18c7d42e901"
down_revision = "f67e6c5467dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reference_sentence_fingerprints",
        sa.Column(
            "fingerprint_type",
            sa.String(length=16),
            server_default="WORD",
            nullable=False,
        ),
    )

    op.drop_constraint(
        "uq_reference_sentence_fingerprint",
        "reference_sentence_fingerprints",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_reference_sentence_fingerprint",
        "reference_sentence_fingerprints",
        [
            "reference_sentence_id",
            "fingerprint_type",
            "ngram_size",
            "fingerprint_hash",
        ],
    )


def downgrade() -> None:
    # Remove non-WORD fingerprints before restoring the old constraint.
    op.execute(
        sa.text(
            "DELETE FROM reference_sentence_fingerprints "
            "WHERE fingerprint_type <> 'WORD'"
        )
    )

    op.drop_constraint(
        "uq_reference_sentence_fingerprint",
        "reference_sentence_fingerprints",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_reference_sentence_fingerprint",
        "reference_sentence_fingerprints",
        [
            "reference_sentence_id",
            "ngram_size",
            "fingerprint_hash",
        ],
    )

    op.drop_column(
        "reference_sentence_fingerprints",
        "fingerprint_type",
    )
