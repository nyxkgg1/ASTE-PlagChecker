"""allow qwen experimental detector type

Revision ID: b8611ab7601d
Revises: d2440b14ca54
Create Date: 2026-11-01 11:20:29.758702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8611ab7601d'
down_revision: Union[str, Sequence[str], None] = 'd2440b14ca54'
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