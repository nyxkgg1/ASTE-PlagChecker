
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings

from app.services.ai_source.base import AIContentSource
from app.services.ai_source.database_source import (
    DatabaseAIContentSource,
)
from app.services.ai_source.dummy_llama_source import (
    DummyLlamaSource,
)


def get_ai_content_source(
    db: Session,
) -> AIContentSource:

    source_type = (
        settings.ai_source_type.strip().upper()
    )

    if source_type == "DUMMY_LLAMA":
        return DummyLlamaSource()

    if source_type == "DATABASE":
        return DatabaseAIContentSource(db=db)

    raise ValueError(
        f"Unsupported AI source type: {source_type}"
    )
