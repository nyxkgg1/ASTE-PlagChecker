from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.reference import (
    ReferenceEmbedding,
    ReferenceSentence,
)
from app.services.embedding_service import generate_embeddings


def create_reference_sentence_embeddings(
    db: Session,
    sentences: list[ReferenceSentence],
    model_id: UUID,
    batch_size: int = 32,
    model_path: str | None = None,
) -> int:
    """
    Generate embeddings for reference sentences
    and store them in PostgreSQL.

    The caller controls the database transaction.
    """

    if not sentences:
        return 0

    valid_sentences = [
        sentence
        for sentence in sentences
        if sentence.normalized_text
        and sentence.normalized_text.strip()
    ]

    if not valid_sentences:
        return 0

    texts = [
        sentence.normalized_text
        for sentence in valid_sentences
    ]

    embeddings = generate_embeddings(
        texts,
        batch_size=batch_size,
        model_path=model_path,
    )

    if len(embeddings) != len(valid_sentences):
        raise ValueError(
            "Embedding count does not match sentence count."
        )

    expected_dimension = settings.embedding_dimension
    sentence_ids = [sentence.id for sentence in valid_sentences]
    existing_embeddings = {
        embedding.sentence_id: embedding
        for embedding in (
            db.query(ReferenceEmbedding)
            .filter(
                ReferenceEmbedding.sentence_id.in_(sentence_ids),
                ReferenceEmbedding.model_id == model_id,
            )
            .all()
        )
    }

    count = 0

    for sentence, embedding in zip(
        valid_sentences,
        embeddings,
    ):

        if len(embedding) != expected_dimension:
            raise ValueError(
                f"Expected embedding dimension "
                f"{expected_dimension}, "
                f"got {len(embedding)}."
            )

        existing = existing_embeddings.get(sentence.id)

        if existing:
            existing.embedding = embedding
            existing.model_id = model_id

        else:
            db.add(
                ReferenceEmbedding(
                    sentence_id=sentence.id,
                    model_id=model_id,
                    embedding=embedding,
                )
            )

        count += 1

    db.flush()

    return count