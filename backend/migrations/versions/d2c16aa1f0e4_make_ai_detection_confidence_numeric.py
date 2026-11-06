"""make ai detection confidence numeric

Revision ID: d2c16aa1f0e4
Revises: ca3d32a83516
Create Date: 2026-10-03 18:36:23.875862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2c16aa1f0e4'
down_revision: Union[str, Sequence[str], None] = 'ca3d32a83516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
