
"""add AI generated content corpus

Revision ID: 4d4e0d87b526
Revises: 66aed157c25e
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision: str = "4d4e0d87b526"
down_revision: Union[str, Sequence[str], None] = "66aed157c25e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # 1. Store AI-generated reference content
    op.create_table(
        "ai_generated_content",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),

        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),

        sa.Column("source_model", sa.String(length=150), nullable=True),
        sa.Column("source_version", sa.String(length=100), nullable=True),

        sa.Column(
            "generation_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_ai_generated_content_hash",
        "ai_generated_content",
        ["content_hash"],
        unique=False,
    )

    # PostgreSQL full-text search index
    op.execute("""
        CREATE INDEX ix_ai_generated_content_fts
        ON ai_generated_content
        USING gin (to_tsvector('english', normalized_text))
    """)

    # 2. Store embeddings generated from corpus content
    op.create_table(
        "ai_generated_content_embeddings",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),

        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "embedding",
            Vector(1024),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["content_id"],
            ["ai_generated_content.id"],
            name="fk_ai_content_embeddings_content",
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model_registry.id"],
            name="fk_ai_content_embeddings_model",
            ondelete="RESTRICT",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "content_id",
            "model_id",
            name="uq_ai_content_embedding_model",
        ),
    )

    op.create_index(
        "ix_ai_content_embeddings_model_id",
        "ai_generated_content_embeddings",
        ["model_id"],
        unique=False,
    )

    # Cosine similarity search
    op.execute("""
        CREATE INDEX ix_ai_content_embeddings_vector_hnsw
        ON ai_generated_content_embeddings
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:

    op.execute(
        "DROP INDEX IF EXISTS ix_ai_content_embeddings_vector_hnsw"
    )

    op.drop_index(
        "ix_ai_content_embeddings_model_id",
        table_name="ai_generated_content_embeddings",
    )

    op.drop_table("ai_generated_content_embeddings")

    op.execute(
        "DROP INDEX IF EXISTS ix_ai_generated_content_fts"
    )

    op.drop_index(
        "ix_ai_generated_content_hash",
        table_name="ai_generated_content",
    )

    op.drop_table("ai_generated_content")
