from __future__ import annotations

import re
import unicodedata

from rapidfuzz.fuzz import ratio


def normalize_heading(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()

    # Remove section numbering
    text = re.sub(
        r"^\s*(\d+(\.\d+)*|[a-z])[\s.)-]+",
        "",
        text,
    )

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_heading_level(text: str) -> int | None:
    """
    Detect hierarchy from numbering.

    Examples:
        1 Introduction       -> 1
        1.1 Background      -> 2
        1.1.1 Methodology   -> 3
    """

    match = re.match(
        r"^\s*(\d+(?:\.\d+)*)[\s.)-]+",
        text,
    )

    if not match:
        return None

    numbering = match.group(1)

    return numbering.count(".") + 1


def heading_similarity(
    detected: str,
    expected: str,
) -> float:

    return (
        ratio(
            normalize_heading(detected),
            normalize_heading(expected),
        )
        / 100.0
    )


def is_probable_heading(line: str) -> bool:

    line = line.strip()

    if not line:
        return False

    if len(line) > 180:
        return False

    words = line.split()

    if len(words) > 20:
        return False

    # Numbered heading
    if re.match(
        r"^\d+(\.\d+)*[\s.)-]+",
        line,
    ):
        return True

    # Uppercase heading
    if line.isupper() and len(words) <= 15:
        return True

    # Title-case heading
    title_case_words = sum(
        1
        for word in words
        if word[:1].isupper()
    )

    if (
        len(words) <= 12
        and title_case_words >= max(
            2,
            len(words) * 0.6,
        )
    ):
        return True

    return False


def detect_headings(pages) -> list[dict]:

    headings = []

    for page in pages:

        lines = page.raw_text.splitlines()

        for line_index, line in enumerate(lines):

            line = line.strip()

            if not is_probable_heading(line):
                continue

            level = extract_heading_level(line)

            if level is None:
                level = 1

            headings.append(
                {
                    "title": line,
                    "page_number": page.page_number,
                    "line_index": line_index,
                    "level": level,
                }
            )

    return headings


def match_heading(
    detected_heading: str,
    template_sections: list[dict],
    threshold: float = 0.72,
):

    best_match = None
    best_score = 0.0

    for section in template_sections:

        score = heading_similarity(
            detected_heading,
            section["name"],
        )

        if score > best_score:
            best_score = score
            best_match = section

    if best_match is None:
        return None, best_score

    if best_score < threshold:
        return None, best_score

    return best_match, best_score