"""baseline existing FTER schema

Revision ID: baseline_fter_001
Revises:
Create Date:
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "baseline_fter_001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration.

    The 25 application tables already exist in PostgreSQL.
    Therefore, this migration intentionally performs no DDL.
    """
    pass


def downgrade() -> None:
    """
    Baseline downgrade intentionally performs no DDL.
    """
    pass