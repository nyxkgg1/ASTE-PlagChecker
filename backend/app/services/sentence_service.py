from __future__ import annotations

import re

import nltk
from nltk.tokenize import sent_tokenize



def split_sentences(text: str) -> list[str]:
    """
    Split document text into sentences while preserving headings
    as separate fragments. Ordinary wrapped lines remain together.
    """
    if not text or not text.strip():
        return []

    sentences: list[str] = []

    paragraphs = re.split(r"\n{2,}", text)

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        lines = [
            line.strip()
            for line in paragraph.splitlines()
            if line.strip()
        ]

        body_lines: list[str] = []

        def flush_body() -> None:
            if not body_lines:
                return

            body = " ".join(body_lines).strip()
            body_lines.clear()

            if not body:
                return

            try:
                parts = sent_tokenize(body)
            except LookupError:
                nltk.download("punkt_tab", quiet=True)
                parts = sent_tokenize(body)

            sentences.extend(
                part.strip()
                for part in parts
                if part.strip()
            )

        for line in lines:
            # Markdown headings should remain separate from body text.
            if re.match(r"^#{1,6}\s+", line):
                flush_body()
                heading = re.sub(r"^#{1,6}\s+", "", line).strip()
                if heading:
                    sentences.append(heading)
            else:
                body_lines.append(line)

        flush_body()

    return sentences


def count_tokens(text: str) -> int:
    """
    Simple whitespace-based token count.

    This is intentionally lightweight.
    The actual NLP tokenizer can be introduced
    later for embeddings and advanced analysis.
    """

    if not text:
        return 0

    return len(
        text.split()
    )