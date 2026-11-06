"""Add scan report approval fields."""

from alembic import op
import sqlalchemy as sa

revision = "REPLACE_WITH_GENERATED_REVISION"
down_revision = "a18c7d42e901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
        ),
    )
    op.add_column(
        "scans",
        sa.Column(
            "admin_approval_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "scans",
        sa.Column(
            "reviewed_by",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.add_column(
        "scans",
        sa.Column(
            "admin_comments",
            sa.Text(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_scans_reviewed_by_users",
        "scans",
        "users",
        ["reviewed_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_scans_reviewed_by_users",
        "scans",
        type_="foreignkey",
    )
    op.drop_column("scans", "admin_comments")
    op.drop_column("scans", "reviewed_by")
    op.drop_column("scans", "admin_approval_date")
    op.drop_column("scans", "approval_status")