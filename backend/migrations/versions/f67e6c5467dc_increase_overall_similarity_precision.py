
"""Increase overall similarity precision.

Revision ID: f67e6c5467dc
Revises: d2c16aa1f0e4
"""

from alembic import op
import sqlalchemy as sa

revision = "f67e6c5467dc"
down_revision = "d2c16aa1f0e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "plagiarism_analyses",
        "overall_similarity",
        existing_type=sa.Numeric(precision=5, scale=2),
        type_=sa.Numeric(precision=10, scale=8),
        existing_nullable=True,
        postgresql_using="overall_similarity::numeric(10, 8)",
    )


def downgrade() -> None:
    op.alter_column(
        "plagiarism_analyses",
        "overall_similarity",
        existing_type=sa.Numeric(precision=10, scale=8),
        type_=sa.Numeric(precision=5, scale=2),
        existing_nullable=True,
        postgresql_using="round(overall_similarity, 2)::numeric(5, 2)",
    )
