"""add AI detector explanations

Revision ID: a81c9e7d42f1
Revises: 4d4e0d87b526
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a81c9e7d42f1"
down_revision: Union[str, Sequence[str], None] = "4d4e0d87b526"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_ai_detector_results_type",
        "ai_detector_results",
        type_="check",
    )

    op.create_check_constraint(
        "ck_ai_detector_results_type",
        "ai_detector_results",
        """
        detector_type IN (
            'CLASSIFIER',
            'CORPUS_MATCH',
            'LINGUISTIC_HEURISTIC',
            'QWEN_EXPERIMENTAL'
        )
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ai_detector_results_type",
        "ai_detector_results",
        type_="check",
    )

    op.create_check_constraint(
        "ck_ai_detector_results_type",
        "ai_detector_results",
        """
        detector_type IN (
            'CLASSIFIER',
            'CORPUS_MATCH',
            'LINGUISTIC_HEURISTIC'
        )
        """,
    )