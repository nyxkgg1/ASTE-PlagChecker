
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.model_registry import ModelRegistry
from app.services.ai_source.base import (
    AIContentSource,
    AISourceDocument,
)
from app.services.embedding_service import generate_embedding


class DatabaseAIContentSource(AIContentSource):
    """
    PostgreSQL hybrid AI corpus search.

    Combines:
    1. PostgreSQL full-text search.
    2. pgvector cosine similarity.
    3. Reciprocal Rank Fusion (RRF).
    """

    RRF_K = 60

    def __init__(self, db: Session):
        self.db = db

    def _get_embedding_model(self) -> ModelRegistry:
        models = (
            self.db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == "Qwen3-0.6B-Base",
                ModelRegistry.version == "0.6B-Base",
                ModelRegistry.model_type == "EMBEDDING",
                ModelRegistry.is_active.is_(True),
            )
            .all()
        )

        if len(models) != 1:
            raise RuntimeError(
                "Expected exactly one active Qwen3-0.6B-Base "
                "embedding model in model_registry."
            )

        return models[0]

    def _full_text_search(
        self,
        query_text: str,
        limit: int,
    ) -> list:
        query = text(
            """
            SELECT
                c.id,
                c.generated_text,
                c.source_model,
                c.source_version,
                c.metadata AS source_metadata,

                ts_rank_cd(
                    to_tsvector('english', c.normalized_text),
                    websearch_to_tsquery('english', :query_text)
                ) AS fts_rank

            FROM ai_generated_content c

            WHERE
                c.is_active IS TRUE
                AND to_tsvector(
                    'english',
                    c.normalized_text
                ) @@ websearch_to_tsquery(
                    'english',
                    :query_text
                )

            ORDER BY
                fts_rank DESC,
                c.id

            LIMIT :limit
            """
        )

        return self.db.execute(
            query,
            {
                "query_text": query_text,
                "limit": limit,
            },
        ).fetchall()

    def _vector_search(
        self,
        query_embedding: list[float],
        model_id,
        limit: int,
    ) -> list:
        query = text(
            """
            SELECT
                c.id,
                c.generated_text,
                c.source_model,
                c.source_version,
                c.metadata AS source_metadata,

                1 - (
                    e.embedding
                    <=> CAST(:query_embedding AS vector)
                ) AS vector_similarity

            FROM ai_generated_content_embeddings e

            JOIN ai_generated_content c
                ON c.id = e.content_id

            WHERE
                c.is_active IS TRUE
                AND e.model_id = :model_id

            ORDER BY
                e.embedding
                <=> CAST(:query_embedding AS vector)

            LIMIT :limit
            """
        )

        return self.db.execute(
            query,
            {
                "query_embedding": str(query_embedding),
                "model_id": model_id,
                "limit": limit,
            },
        ).fetchall()

    def search(
        self,
        query_text: str,
        limit: int = 10,
    ) -> list[AISourceDocument]:

        if not query_text or not query_text.strip():
            return []

        if limit <= 0:
            return []

        if limit > 100:
            raise ValueError(
                "Search limit cannot exceed 100."
            )

        # Retrieve a larger candidate pool from both methods.
        candidate_limit = min(limit * 3, 100)

        # -------------------------------------------------
        # 1. Full-text retrieval
        # -------------------------------------------------

        fts_rows = self._full_text_search(
            query_text=query_text,
            limit=candidate_limit,
        )

        # -------------------------------------------------
        # 2. Generate query embedding
        # -------------------------------------------------

        query_embedding = generate_embedding(query_text)

        if not query_embedding:
            return []

        if len(query_embedding) != settings.embedding_dimension:
            raise ValueError(
                f"Query embedding dimension mismatch: "
                f"expected {settings.embedding_dimension}, "
                f"received {len(query_embedding)}."
            )

        model = self._get_embedding_model()

        # -------------------------------------------------
        # 3. Vector retrieval
        # -------------------------------------------------

        vector_rows = self._vector_search(
            query_embedding=query_embedding,
            model_id=model.id,
            limit=candidate_limit,
        )

        # -------------------------------------------------
        # 4. Merge using Reciprocal Rank Fusion
        # -------------------------------------------------

        candidates = {}

        for rank, row in enumerate(fts_rows, start=1):
            key = str(row.id)

            if key not in candidates:
                candidates[key] = {
                    "row": row,
                    "rrf_score": 0.0,
                    "fts_rank": None,
                    "vector_rank": None,
                    "vector_similarity": None,
                }

            candidates[key]["rrf_score"] += (
                1.0 / (self.RRF_K + rank)
            )

            candidates[key]["fts_rank"] = rank

        for rank, row in enumerate(vector_rows, start=1):
            key = str(row.id)

            if key not in candidates:
                candidates[key] = {
                    "row": row,
                    "rrf_score": 0.0,
                    "fts_rank": None,
                    "vector_rank": None,
                    "vector_similarity": None,
                }

            candidates[key]["rrf_score"] += (
                1.0 / (self.RRF_K + rank)
            )

            candidates[key]["vector_rank"] = rank

            candidates[key]["vector_similarity"] = float(
                row.vector_similarity
            )

        ranked_candidates = sorted(
            candidates.values(),
            key=lambda item: item["rrf_score"],
            reverse=True,
        )

        # -------------------------------------------------
        # 5. Convert to AISourceDocument
        # -------------------------------------------------

        results = []

        for item in ranked_candidates[:limit]:
            row = item["row"]

            metadata = (
                dict(row.source_metadata)
                if isinstance(row.source_metadata, dict)
                else {}
            )

            metadata["source_model"] = row.source_model
            metadata["source_version"] = row.source_version

            metadata["retrieval"] = {
                "method": "HYBRID_RRF",
                "rrf_score": item["rrf_score"],
                "fts_rank": item["fts_rank"],
                "vector_rank": item["vector_rank"],
                "vector_similarity": item["vector_similarity"],
            }

            results.append(
                AISourceDocument(
                    source_id=str(row.id),
                    text=str(row.generated_text),
                    metadata=metadata,
                )
            )

        return results
