from __future__ import annotations

from app.services.ai_source.base import (
    AIContentSource,
    AISourceDocument,
)


class DummyLlamaSource(AIContentSource):
    """
    Development-only AI content source.

    This represents content that would normally come from
    a local Llama/VayuGPT generated-content repository.
    """

    def __init__(self):
        self.documents = [
            AISourceDocument(
                source_id="llama-demo-001",
                text=(
                    "The purpose of flight testing is to verify the "
                    "performance, handling characteristics, structural "
                    "integrity and operational suitability of an aircraft "
                    "under defined test conditions."
                ),
                metadata={
                    "model": "llama",
                    "source": "dummy",
                },
            ),
            AISourceDocument(
                source_id="llama-demo-002",
                text=(
                    "Flight testing is conducted to evaluate aircraft "
                    "performance and handling characteristics against "
                    "specified design requirements."
                ),
                metadata={
                    "model": "llama",
                    "source": "dummy",
                },
            ),
            AISourceDocument(
                source_id="llama-demo-003",
                text=(
                    "Aircraft evaluation involves systematic measurement "
                    "of performance parameters, handling qualities and "
                    "operational characteristics."
                ),
                metadata={
                    "model": "llama",
                    "source": "dummy",
                },
            ),
        ]

    def search(
        self,
        query_text: str,
        limit: int = 10,
    ) -> list[AISourceDocument]:

        # For the first development version we simply return
        # the local dummy corpus.

        if not query_text or not query_text.strip():
            return []

        return self.documents[:limit]