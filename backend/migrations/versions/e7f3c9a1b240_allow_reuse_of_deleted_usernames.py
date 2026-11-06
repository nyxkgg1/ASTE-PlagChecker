"""Allow deleted usernames to be reused."""

from alembic import op
import sqlalchemy as sa

revision = "e7f3c9a1b240"
down_revision = "REPLACE_WITH_GENERATED_REVISION"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "users_username_key",
        "users",
        type_="unique",
    )
    op.create_index(
        "uq_users_username_not_deleted",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("status <> 'DELETED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_users_username_not_deleted",
        table_name="users",
    )
    op.create_unique_constraint(
        "users_username_key",
        "users",
        ["username"],
    )
