from __future__ import annotations

import re
from difflib import SequenceMatcher


def tokenize_with_positions(text: str) -> list[dict]:
    """
    Tokenize text while preserving character positions.

    Example:

        "Aircraft performance was recorded"

    Returns tokens with:
        token
        start
        end
    """

    if not text:
        return []

    tokens = []

    for match in re.finditer(
        r"\S+",
        text,
    ):
        tokens.append(
            {
                "token": match.group(),
                "start": match.start(),
                "end": match.end(),
            }
        )

    return tokens


def normalize_token(token: str) -> str:
    """
    Normalize a token for comparison.

    This is intentionally lightweight.
    """

    token = token.lower()

    token = re.sub(
        r"[^\w]",
        "",
        token,
    )

    return token


def find_matching_token_ranges(
    scan_text: str,
    reference_text: str,
    min_match_length: int = 3,
) -> list[dict]:
    """
    Find matching token ranges between scan text
    and reference text.

    The function returns character positions in the
    scan text that have corresponding matching tokens
    in the reference text.
    """

    scan_tokens = tokenize_with_positions(
        scan_text
    )

    reference_tokens = tokenize_with_positions(
        reference_text
    )

    scan_normalized = [
        normalize_token(
            item["token"]
        )
        for item in scan_tokens
    ]

    reference_normalized = [
        normalize_token(
            item["token"]
        )
        for item in reference_tokens
    ]

    matcher = SequenceMatcher(
        None,
        scan_normalized,
        reference_normalized,
        autojunk=False,
    )

    ranges = []

    for (
        scan_start,
        reference_start,
        size,
    ) in matcher.get_matching_blocks():

        if size < min_match_length:
            continue

        scan_end = (
            scan_start + size
        )

        if scan_start >= len(
            scan_tokens
        ):
            continue

        final_scan_token = scan_tokens[
            min(
                scan_end - 1,
                len(scan_tokens) - 1,
            )
        ]

        start_position = scan_tokens[
            scan_start
        ]["start"]

        end_position = (
            final_scan_token["end"]
        )

        ranges.append(
            {
                "start": start_position,
                "end": end_position,
                "text": scan_text[
                    start_position:end_position
                ],
                "token_count": size,
                "reference_start_token": (
                    reference_start
                ),
            }
        )

    return ranges


def merge_overlapping_ranges(
    ranges: list[dict],
) -> list[dict]:
    """
    Merge overlapping or adjacent
    character ranges.
    """

    if not ranges:
        return []

    sorted_ranges = sorted(
        ranges,
        key=lambda item: item["start"],
    )

    merged = [
        {
            "start": sorted_ranges[0][
                "start"
            ],
            "end": sorted_ranges[0][
                "end"
            ],
        }
    ]

    for current in sorted_ranges[1:]:

        previous = merged[-1]

        if (
            current["start"]
            <= previous["end"]
        ):
            previous["end"] = max(
                previous["end"],
                current["end"],
            )

        else:
            merged.append(
                {
                    "start": current[
                        "start"
                    ],
                    "end": current[
                        "end"
                    ],
                }
            )

    return [
        {
            "start": item["start"],
            "end": item["end"],
        }
        for item in merged
    ]


def build_highlight_segments(
    text: str,
    ranges: list[dict],
) -> list[dict]:
    """
    Convert character ranges into frontend-ready
    text segments.

    Example:

        [
            {
                "text": "The aircraft ",
                "matched": False
            },
            {
                "text": "performance was recorded",
                "matched": True
            }
        ]
    """

    if not text:
        return []

    if not ranges:
        return [
            {
                "text": text,
                "matched": False,
            }
        ]

    merged_ranges = merge_overlapping_ranges(
        ranges
    )

    segments = []

    current_position = 0

    for item in merged_ranges:

        start = item["start"]
        end = item["end"]

        if start > current_position:

            segments.append(
                {
                    "text": text[
                        current_position:start
                    ],
                    "matched": False,
                }
            )

        segments.append(
            {
                "text": text[
                    start:end
                ],
                "matched": True,
            }
        )

        current_position = end

    if current_position < len(text):

        segments.append(
            {
                "text": text[
                    current_position:
                ],
                "matched": False,
            }
        )

    return segments


def generate_highlighting(
    scan_text: str,
    reference_text: str,
) -> dict:
    """
    Generate frontend-ready highlighting information.
    """

    if not scan_text:
        return {
            "segments": [],
            "matched": False,
            "matched_character_count": 0,
            "total_character_count": 0,
            "character_coverage_percentage": 0.0,
        }

    ranges = find_matching_token_ranges(
        scan_text=scan_text,
        reference_text=reference_text,
    )

    segments = build_highlight_segments(
        text=scan_text,
        ranges=ranges,
    )

    matched_character_count = sum(
        item["end"] - item["start"]
        for item in merge_overlapping_ranges(
            ranges
        )
    )

    total_character_count = len(
        scan_text
    )

    coverage = (
        matched_character_count
        / total_character_count
        * 100
        if total_character_count
        else 0.0
    )

    return {
        "segments": segments,
        "matched": bool(ranges),
        "matched_character_count": (
            matched_character_count
        ),
        "total_character_count": (
            total_character_count
        ),
        "character_coverage_percentage": round(
            coverage,
            2,
        ),
    }