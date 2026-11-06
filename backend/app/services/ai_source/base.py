from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AISourceDocument:
    source_id: str
    text: str
    metadata: dict


class AIContentSource(ABC):

    @abstractmethod
    def search(
        self,
        query_text: str,
        limit: int = 10,
    ) -> list[AISourceDocument]:
        """
        Search AI-generated content available to the
        offline FTER system.
        """
        raise NotImplementedError