"""add qwen experimental detector

Revision ID: 81749de3fa21
Revises: a81c9e7d42f1
Create Date: 2026-11-01 11:12:35.548136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81749de3fa21'
down_revision: Union[str, Sequence[str], None] = 'a81c9e7d42f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
