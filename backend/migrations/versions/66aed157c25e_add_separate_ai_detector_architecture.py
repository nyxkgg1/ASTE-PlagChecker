"""Add separate AI detector architecture.

Revision ID: 66aed157c25e
Revises: f2a0c6d93e81
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "66aed157c25e"
down_revision: Union[str, Sequence[str], None] = "f2a0c6d93e81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. One AI analysis execution per scan run.
    op.create_table(
        "ai_analysis_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("scan_id", sa.UUID(), nullable=False),
        sa.Column("initiated_by", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="PROCESSING",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            """
            status IN (
                'PROCESSING',
                'COMPLETED',
                'PARTIAL_COMPLETED',
                'FAILED',
                'NOT_CONFIGURED'
            )
            """,
            name="ck_ai_analysis_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scans.id"],
            name="fk_ai_analysis_runs_scan",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["initiated_by"],
            ["users.id"],
            name="fk_ai_analysis_runs_initiated_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_ai_analysis_runs_scan_created",
        "ai_analysis_runs",
        ["scan_id", "created_at"],
    )
    op.create_index(
        "idx_ai_analysis_runs_status",
        "ai_analysis_runs",
        ["status"],
    )

    # 2. Independent result for each detector in a run.
    op.create_table(
        "ai_detector_results",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("detector_type", sa.String(length=40), nullable=False),
        sa.Column("detector_version", sa.String(length=100), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="PROCESSING",
            nullable=False,
        ),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_semantics", sa.String(length=60), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            """
            detector_type IN (
                'CLASSIFIER',
                'CORPUS_MATCH',
                'LINGUISTIC_HEURISTIC'
            )
            """,
            name="ck_ai_detector_results_type",
        ),
        sa.CheckConstraint(
            """
            status IN (
                'PROCESSING',
                'COMPLETED',
                'FAILED',
                'NOT_CONFIGURED',
                'NOT_ANALYZED'
            )
            """,
            name="ck_ai_detector_results_status",
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_ai_detector_results_score_range",
        ),
        sa.CheckConstraint(
            """
            confidence IS NULL
            OR (confidence >= 0 AND confidence <= 1)
            """,
            name="ck_ai_detector_results_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["ai_analysis_runs.id"],
            name="fk_ai_detector_results_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model_registry.id"],
            name="fk_ai_detector_results_model",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "detector_type",
            name="uq_ai_detector_result_run_type",
        ),
    )

    op.create_index(
        "idx_ai_detector_results_run",
        "ai_detector_results",
        ["run_id"],
    )
    op.create_index(
        "idx_ai_detector_results_type_status",
        "ai_detector_results",
        ["detector_type", "status"],
    )

    # 3. Sentence-level evidence supporting a detector result.
    op.create_table(
        "ai_detector_evidence",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("detector_result_id", sa.UUID(), nullable=False),
        sa.Column("sentence_id", sa.UUID(), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("evidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            """
            evidence_score IS NULL
            OR (evidence_score >= 0 AND evidence_score <= 100)
            """,
            name="ck_ai_detector_evidence_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["detector_result_id"],
            ["ai_detector_results.id"],
            name="fk_ai_detector_evidence_result",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sentence_id"],
            ["scan_sentences.id"],
            name="fk_ai_detector_evidence_sentence",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_ai_detector_evidence_result",
        "ai_detector_evidence",
        ["detector_result_id"],
    )
    op.create_index(
        "idx_ai_detector_evidence_sentence",
        "ai_detector_evidence",
        ["sentence_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_ai_detector_evidence_sentence",
        table_name="ai_detector_evidence",
    )
    op.drop_index(
        "idx_ai_detector_evidence_result",
        table_name="ai_detector_evidence",
    )
    op.drop_table("ai_detector_evidence")

    op.drop_index(
        "idx_ai_detector_results_type_status",
        table_name="ai_detector_results",
    )
    op.drop_index(
        "idx_ai_detector_results_run",
        table_name="ai_detector_results",
    )
    op.drop_table("ai_detector_results")

    op.drop_index(
        "idx_ai_analysis_runs_status",
        table_name="ai_analysis_runs",
    )
    op.drop_index(
        "idx_ai_analysis_runs_scan_created",
        table_name="ai_analysis_runs",
    )
    op.drop_table("ai_analysis_runs")
