from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.reference import (
    ReferenceDocument,
    ReferenceSentence,
    ReferenceDocumentVersion,
)
from app.services.plagiarism_model_service import (
    get_selected_embedding_model,
)

from app.services.document_extraction_service import extract_document
from app.services.text_normalization_service import normalize_text
from app.services.sentence_service import split_sentences
from app.services.reference_fingerprint_service import (
    index_reference_sentence,
)
from app.services.reference_embedding_service import (
    create_reference_sentence_embeddings,
)


def get_current_version(
    db: Session,
    reference_document: ReferenceDocument,
) -> ReferenceDocumentVersion | None:

    return (
        db.query(ReferenceDocumentVersion)
        .filter(
            ReferenceDocumentVersion.reference_document_id
            == reference_document.id,
            ReferenceDocumentVersion.version_number
            == reference_document.current_version,
        )
        .first()
    )


def index_reference_document(
    db: Session,
    reference_document: ReferenceDocument,
) -> int:

    # ---------------------------------------------------------
    # 1. Get current reference document version
    # ---------------------------------------------------------

    current_version = get_current_version(
        db,
        reference_document,
    )

    if not current_version:
        raise ValueError(
            "Current reference document version was not found."
        )

    # ---------------------------------------------------------
    # 2. Get the configured plagiarism embedding model
    # ---------------------------------------------------------

    (
        embedding_model,
        local_embedding_model,
    ) = get_selected_embedding_model(db)

    # ---------------------------------------------------------
    # 3. Remove previously indexed sentences
    # ---------------------------------------------------------

    db.query(ReferenceSentence).filter(
        ReferenceSentence.reference_document_id
        == reference_document.id
    ).delete(
        synchronize_session=False
    )

    # ---------------------------------------------------------
    # 4. Extract document
    # ---------------------------------------------------------

    pages = extract_document(
        current_version.file_path
    )

    reference_sentences: list[ReferenceSentence] = []

    # ---------------------------------------------------------
    # 5. Extract + normalize + split sentences
    # ---------------------------------------------------------

    for page in pages:

        normalized_page_text = normalize_text(
            page.raw_text or ""
        )

        if not normalized_page_text:
            continue

        sentences = split_sentences(
            normalized_page_text
        )

        for sentence_index, sentence in enumerate(
            sentences,
            start=1,
        ):

            sentence_text = normalize_text(
                sentence
            )

            if not sentence_text:
                continue

            reference_sentence = ReferenceSentence(
                reference_document_id=reference_document.id,
                version_id=current_version.id,
                page_number=page.page_number,
                section_title=None,
                sentence_index=sentence_index,
                raw_text=sentence,
                normalized_text=sentence_text,
            )

            db.add(reference_sentence)

            reference_sentences.append(
                reference_sentence
            )

    # ---------------------------------------------------------
    # 6. Flush so sentence UUIDs are generated
    # ---------------------------------------------------------

    db.flush()

    # ---------------------------------------------------------
    # 7. Generate plagiarism fingerprints
    # ---------------------------------------------------------

    for reference_sentence in reference_sentences:

        index_reference_sentence(
            db,
            reference_sentence,
        )

    # ---------------------------------------------------------
    # 8. Generate Qwen3 embeddings
    # ---------------------------------------------------------

    embedding_count = (
        create_reference_sentence_embeddings(
            db=db,
            sentences=reference_sentences,
            model_id=embedding_model.id,
            model_path=str(local_embedding_model.path),
        )
    )

    # ---------------------------------------------------------
    # 9. Commit everything
    # ---------------------------------------------------------

    db.commit()

    print(
        f"Reference indexing completed: "
        f"{len(reference_sentences)} sentences, "
        f"{embedding_count} embeddings."
    )

    return len(reference_sentences)