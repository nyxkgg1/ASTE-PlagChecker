from alembic import op


revision = "ADD_HNSW_INDEX"
down_revision = "b3ea32265f96"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_reference_embeddings_embedding_hnsw
        ON reference_embeddings
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS
        ix_reference_embeddings_embedding_hnsw
        """
    )