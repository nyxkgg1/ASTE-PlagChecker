"""Allow non-analyzed AI detector results."""

from alembic import op
import sqlalchemy as sa


revision = "f2a0c6d93e81"
down_revision = "e7f3c9a1b240"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ai_status_check",
        "ai_detection_results",
        type_="check",
    )
    op.create_check_constraint(
        "ai_status_check",
        "ai_detection_results",
        sa.text(
            "status IN "
            "('PROCESSING', 'COMPLETED', 'FAILED', "
            "'NOT_CONFIGURED', 'NOT_ANALYZED')"
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE ai_detection_results
        SET status = 'FAILED'
        WHERE status IN ('NOT_CONFIGURED', 'NOT_ANALYZED')
        """
    )
    op.drop_constraint(
        "ai_status_check",
        "ai_detection_results",
        type_="check",
    )
    op.create_check_constraint(
        "ai_status_check",
        "ai_detection_results",
        sa.text("status IN ('PROCESSING', 'COMPLETED', 'FAILED')"),
    )
