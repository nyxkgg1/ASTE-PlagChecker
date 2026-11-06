from __future__ import annotations

import re
import unicodedata


ZERO_WIDTH_CHARS = (
    "\u200b",
    "\u200c",
    "\u200d",
    "\ufeff",
)


def normalize_text(text: str) -> str:
    if not text:
        return ""

    # Unicode normalization
    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    # Remove zero-width / invisible characters
    for character in ZERO_WIDTH_CHARS:
        text = text.replace(character, "")

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Collapse repeated spaces
    text = re.sub(
        r"[ \u00a0]+",
        " ",
        text,
    )

    # Normalize excessive blank lines
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    # Remove spaces around newlines
    # Preserve word boundaries when a line break separates words.
# Then remove surrounding spaces from the newline.
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)
    text = re.sub(r" *\n *", "\n", text)

    return text.strip()