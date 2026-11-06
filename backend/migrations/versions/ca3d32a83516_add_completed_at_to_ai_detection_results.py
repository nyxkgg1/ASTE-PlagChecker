from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ca3d32a83516"
down_revision: Union[str, Sequence[str], None] = "ADD_HNSW_INDEX"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_detection_results",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "ai_detection_results",
        "completed_at",
    )