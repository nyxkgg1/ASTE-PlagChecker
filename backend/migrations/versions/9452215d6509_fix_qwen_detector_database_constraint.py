"""fix qwen detector database constraint

Revision ID: 9452215d6509
Revises: b8611ab7601d
Create Date: 2026-11-01 11:26:11.878465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9452215d6509'
down_revision: Union[str, Sequence[str], None] = 'b8611ab7601d'
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