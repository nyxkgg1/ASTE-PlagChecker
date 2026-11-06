from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.embedding_service import generate_embedding
from app.services.plagiarism_model_service import (
    get_selected_embedding_model,
)


def search_reference_embeddings(
    db: Session,
    query_text: str,
    limit: int = 5,
    min_similarity: float = 0.0,
) -> list[dict]:
    """
    Search reference sentence embeddings using
    pgvector cosine similarity.

    Returns the most semantically similar reference
    sentences.
    """

    if not query_text or not query_text.strip():
        return []

    if limit <= 0:
        return []

    # --------------------------------------------------------
    # Generate query embedding
    # --------------------------------------------------------

    model, local_model = get_selected_embedding_model(db)
    query_embedding = generate_embedding(query_text, local_model.path)

    if not query_embedding:
        return []

    # --------------------------------------------------------
    # Verify embedding dimension
    # --------------------------------------------------------

    if len(query_embedding) != settings.embedding_dimension:
        raise ValueError(
            f"Query embedding dimension is "
            f"{len(query_embedding)}, expected "
            f"{settings.embedding_dimension}."
        )

    # --------------------------------------------------------
    # pgvector cosine similarity search
    #
    # <=> = cosine distance
    #
    # similarity = 1 - cosine distance
    # --------------------------------------------------------

    query = text(
        """
        SELECT
            re.id AS embedding_id,
            re.sentence_id,
            rs.reference_document_id,
            rs.page_number,
            rs.section_title,
            rs.sentence_index,
            rs.raw_text,
            rs.normalized_text,

            1 - (re.embedding <=> CAST(:query_embedding AS vector))
                AS similarity

        FROM reference_embeddings re

        JOIN reference_sentences rs
            ON rs.id = re.sentence_id

        JOIN reference_documents rd
            ON rd.id = rs.reference_document_id

        WHERE
            re.model_id = :model_id
            AND rd.status = 'ACTIVE'

        ORDER BY
            re.embedding <=> CAST(:query_embedding AS vector)

        LIMIT :limit
        """
    )

    rows = db.execute(
        query,
        {
            "query_embedding": str(query_embedding),
            "model_id": model.id,
            "limit": limit,
        },
    ).fetchall()

    # --------------------------------------------------------
    # Convert SQL rows to dictionaries
    # --------------------------------------------------------

    results = []

    for row in rows:

        similarity = float(
            row.similarity
        )

        if similarity < min_similarity:
            continue

        results.append(
            {
                "embedding_id": row.embedding_id,
                "sentence_id": row.sentence_id,
                "reference_document_id": (
                    row.reference_document_id
                ),
                "page_number": row.page_number,
                "section_title": row.section_title,
                "sentence_index": row.sentence_index,
                "raw_text": row.raw_text,
                "normalized_text": row.normalized_text,
                "similarity": similarity,
            }
        )

    return results