from __future__ import annotations

import re
from collections import defaultdict


_SUMMARY_RE = re.compile(r"^(?:executive\s+)?summary\s*:?$", re.IGNORECASE)
_PARAGRAPH_RE = re.compile(
    r"^(?:para(?:graph)?\s+)?(\d{1,3})[.:)]?\s+(.+)$",
    re.IGNORECASE,
)
_SUBHEADING_RE = re.compile(r"^\d{1,3}\.\d+(?:\.\d+)*[.)]?\s+\S")
_IGNORED_SECTION_RE = re.compile(
    r"^(?:table\s+of\s+contents|contents|index|"
    r"list\s+of\s+(?:tables|figures)|tables?|figures?)\s*:??$",
    re.IGNORECASE,
)
_KNOWN_HEADING_RE = re.compile(
    r"^(?:introduction|background|aim|objectives?|scope|"
    r"methodology|methods?|results?|discussion|conclusion|"
    r"recommendations?|references?|bibliography|appendix|"
    r"annex(?:ure)?|acknowledg(?:e)?ments?)$",
    re.IGNORECASE,
)
_MAIN_SECTION_RE = re.compile(
    r"^\s*(?:para(?:graph)?\s*)?(\d{1,2})[.:)]?\s+(.+?)\s*$",
    re.IGNORECASE,
)
_SUBSECTION_RE = re.compile(
    r"^\s*(?:para(?:graph)?\s*)?(\d{1,2})\.(\d+(?:\.\d+)*)[.:)]?\s+(.+?)\s*$",
    re.IGNORECASE,
)
_CLASSIFICATION_RE = re.compile(
    r"^(?:instr(?:uctor)?\s+secret|restricted|confidential|secret|top secret)$",
    re.IGNORECASE,
)
_PAGE_MARKER_RE = re.compile(
    r"^(?:pg\.?\s*:?\s*)?\d{1,4}\s*$",
    re.IGNORECASE,
)
FTER_FORMAT_CONFIG = {
    "minimum_markers": 7,
    "markers": {
        "establishment": re.compile(
            r"aircraft\s*(?:&|and)\s*systems\s+testing\s+establishment",
            re.IGNORECASE,
        ),
        "crest": re.compile(r"\bcrest\b", re.IGNORECASE),
        "report_number": re.compile(
            r"flight\s+test\s+and\s+evaluation\s+report\s+no\.?\s+"
            r"[a-z0-9-]+(?:\s*/\s*[a-z0-9-]+){2,}",
            re.IGNORECASE,
        ),
        "summary": re.compile(
            r"(?m)^\s*(?:executive\s+)?summary\s*:?\s*$",
            re.IGNORECASE,
        ),
        "contents": re.compile(
            r"(?m)^\s*table\s+of\s+contents\s*:?\s*$",
            re.IGNORECASE,
        ),
        "appendices": re.compile(
            r"(?m)^\s*list\s+of\s+appendices(?:\s*\([^)]*\))?\s*:?\s*$",
            re.IGNORECASE,
        ),
        "tables": re.compile(
            r"(?m)^\s*list\s+of\s+tables(?:\s*\([^)]*\))?\s*:?\s*$",
            re.IGNORECASE,
        ),
        "figures": re.compile(
            r"(?m)^\s*list\s+of\s+figures(?:\s*\([^)]*\))?\s*:?\s*$",
            re.IGNORECASE,
        ),
        "paragraph_1": re.compile(
            r"(?m)^\s*1[.)]?\s+introduction\b",
            re.IGNORECASE,
        ),
        "paragraph_2": re.compile(
            r"(?m)^\s*2[.)]?\s+conditions?\s+relevant\s+to\s+tests?\b",
            re.IGNORECASE,
        ),
        "paragraph_3": re.compile(
            r"(?m)^\s*3[.)]?\s+analysis\s+and\s+results?\b",
            re.IGNORECASE,
        ),
        "paragraph_4": re.compile(
            r"(?m)^\s*4[.)]?\s+recommendations?\b",
            re.IGNORECASE,
        ),
    },
    "sections": {
        "summary": {"title": "Summary", "default_selected": True},
        "introduction": {"title": "Para 1: Introduction", "default_selected": False},
        "conditions": {
            "title": "Para 2: Conditions Relevant to Tests",
            "default_selected": False,
        },
        "analysis": {
            "title": "Para 3: Analysis and Results",
            "default_selected": True,
        },
        "recommendations": {
            "title": "Para 4: Recommendations",
            "default_selected": True,
        },
    },
    "front_matter": {
        "contents": {
            "title": "Table of Contents",
            "pattern": re.compile(
                r"^(?:table\s+of\s+)?contents(?:\s*\([^)]*\))?$",
                re.IGNORECASE,
            ),
        },
        "appendices": {
            "title": "List of Appendices",
            "pattern": re.compile(
                r"^(?:list\s+of\s+)?appendices(?:\s*\([^)]*\))?$",
                re.IGNORECASE,
            ),
        },
        "tables": {
            "title": "List of Tables",
            "pattern": re.compile(
                r"^list\s+of\s+tables(?:\s*\([^)]*\))?$",
                re.IGNORECASE,
            ),
        },
        "figures": {
            "title": "List of Figures",
            "pattern": re.compile(
                r"^list\s+of\s+figures(?:\s*\([^)]*\))?$",
                re.IGNORECASE,
            ),
        },
    },
}


def _is_fter_document(pages: list[dict]) -> bool:
    all_text = "\n".join(page.get("raw_text", "") for page in pages)
    markers = FTER_FORMAT_CONFIG["markers"]
    found = sum(bool(marker.search(all_text)) for marker in markers.values())
    classification_pages = sum(
        1
        for page in pages
        if re.search(r"\binstr\s+secret\b", page.get("raw_text", ""), re.IGNORECASE)
    )
    found += classification_pages >= 2
    return found >= FTER_FORMAT_CONFIG["minimum_markers"]


def _section_kind(title: str) -> str | None:
    normalized = title.casefold().strip(" :.")
    if _SUMMARY_RE.fullmatch(normalized):
        return "summary"
    if re.fullmatch(
        r"(?:analysis\s+(?:and|&)\s+results?|results?\s+(?:and|&)\s+analysis)",
        normalized,
    ):
        return "analysis"
    if re.fullmatch(r"recommendations?", normalized):
        return "recommendations"
    if re.fullmatch(r"conditions?\s+relevant\s+to\s+tests?", normalized):
        return "conditions"
    if re.fullmatch(r"introduction", normalized):
        return "introduction"
    return None


def _extract_fter_paragraphs(pages: list[dict]) -> list[dict]:
    paragraphs: list[dict] = []
    current_section: str | None = None
    current_subsection: str | None = None
    current_front_matter: str | None = None
    current_page = 1
    body: list[str] = []
    section_counts: defaultdict[str, int] = defaultdict(int)
    id_counts: defaultdict[str, int] = defaultdict(int)
    used_ids: set[str] = set()
    ignore_front_matter = False

    def unique_id(base_id: str) -> str:
        """Return a unique ID while preserving the original ID when possible."""
        if base_id not in used_ids:
            used_ids.add(base_id)
            id_counts[base_id] = 1
            return base_id

        suffix = id_counts[base_id] + 1
        candidate = f"{base_id}:{suffix}"

        while candidate in used_ids:
            suffix += 1
            candidate = f"{base_id}:{suffix}"

        id_counts[base_id] = suffix
        used_ids.add(candidate)
        return candidate

    def flush() -> None:
        nonlocal body
        text = " ".join(body).strip()
        body = []
        if not text:
            return

        if current_front_matter is not None:
            config = FTER_FORMAT_CONFIG["front_matter"][current_front_matter]
            paragraphs.append({
                "id": unique_id(f"front:{current_front_matter}"),
                "label": config["title"],
                "paragraph_number": None,
                "page_number": current_page,
                "text": text,
                "section_id": f"front:{current_front_matter}",
                "section_title": config["title"],
                "parent_section_id": "front-matter",
                "parent_section_title": "Front matter",
                "is_front_matter": True,
            })
            return

        if current_section is None:
            return
        if current_section == "summary":
            item_id = "summary"
            label = FTER_FORMAT_CONFIG["sections"]["summary"]["title"]
            paragraph_number = None
            section_id = "summary"
        elif current_section == "analysis":
            if current_subsection:
                item_id = f"analysis:{current_subsection}"
                label = f"{current_subsection}"
            else:
                section_counts[current_section] += 1
                item_id = f"analysis:paragraph:{section_counts[current_section]}"
                label = f"Para 3 paragraph {section_counts[current_section]}"
            paragraph_number = 3
            section_id = "analysis"
        elif current_section == "recommendations":
            item_id = "recommendations"
            label = FTER_FORMAT_CONFIG["sections"]["recommendations"]["title"]
            paragraph_number = 4
            section_id = "recommendations"
        elif current_section == "conditions":
            section_counts[current_section] += 1
            item_id = f"conditions:{section_counts[current_section]}"
            label = f"Para 2 paragraph {section_counts[current_section]}"
            paragraph_number = 2
            section_id = "conditions"
        elif current_section == "introduction":
            section_counts[current_section] += 1
            item_id = f"introduction:{section_counts[current_section]}"
            label = f"Para 1 paragraph {section_counts[current_section]}"
            paragraph_number = 1
            section_id = "introduction"
        else:
            return

        paragraphs.append({
            "id": unique_id(item_id),
            "label": label,
            "paragraph_number": paragraph_number,
            "page_number": current_page,
            "text": text,
            "section_id": section_id,
            "section_title": FTER_FORMAT_CONFIG["sections"][current_section]["title"],
            "parent_section_id": None,
            "parent_section_title": None,
            "is_front_matter": False,
        })

    for page in pages:
        page_number = int(page["page_number"])
        heading_lines = {
            _clean_line(line).casefold()
            for line in page.get("heading_lines", [])
        }
        for raw_line in (page.get("raw_text") or "").splitlines():
            raw_is_table_row = _is_table_row(raw_line)
            line = _clean_line(raw_line)
            if not line or _is_classification_header(line) or _PAGE_MARKER_RE.fullmatch(line):
                continue
            if line.casefold() == "index":
                flush()
                current_section = None
                current_subsection = None
                current_front_matter = None
                ignore_front_matter = True
                continue
            front_matter = next(
                (
                    key
                    for key, config in FTER_FORMAT_CONFIG["front_matter"].items()
                    if config["pattern"].fullmatch(line)
                ),
                None,
            )
            if front_matter:
                flush()
                current_section = None
                current_subsection = None
                current_front_matter = front_matter
                ignore_front_matter = False
                current_page = page_number
                continue

            if current_front_matter is not None and _is_contents_entry(line):
                if not body:
                    current_page = page_number
                body.append(re.sub(r"\s*\.{2,}\s*\d{1,4}\s*$", "", line))
                continue

            numbered_heading = _MAIN_SECTION_RE.match(line)
            section_title = numbered_heading.group(2) if numbered_heading else line
            section = _section_kind(section_title)

            if ignore_front_matter:
                if _is_contents_entry(line):
                    continue
                if section:
                    ignore_front_matter = False
                elif line.casefold() in heading_lines and not _is_table_row(line):
                    continue
                else:
                    continue

            if section:
                flush()
                current_front_matter = None
                current_section = section
                current_subsection = None
                current_page = page_number
                continue

            if current_front_matter is not None:
                if raw_is_table_row and not _is_contents_entry(line):
                    continue
                if not body:
                    current_page = page_number
                body.append(re.sub(r"\s*\.{2,}\s*\d{1,4}\s*$", "", line))
                continue

            if current_section in {"summary", "analysis", "conditions", "introduction", "recommendations"}:
                subsection = _SUBSECTION_RE.match(line)
                if subsection:
                    flush()
                    if current_section == "analysis":
                        current_subsection = (
                            f"{subsection.group(1)}.{subsection.group(2)}"
                        )
                    else:
                        current_subsection = None
                    current_page = page_number
                    continue

                if _is_heading(line, heading_lines) or raw_is_table_row or _is_table_row(line):
                    flush()
                    continue

                if current_section == "analysis" and current_subsection is None:
                    paragraph_match = _PARAGRAPH_RE.match(line)
                    if paragraph_match:
                        flush()
                        current_page = page_number
                        body.append(paragraph_match.group(2))
                        continue

                if not body:
                    current_page = page_number
                body.append(line)

    flush()
    return paragraphs


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\u00a0", " ")).strip()


def _is_heading(line: str, heading_lines: set[str] | None = None) -> bool:
    if heading_lines and line.casefold() in heading_lines:
        return True
    if _SUMMARY_RE.fullmatch(line) or _IGNORED_SECTION_RE.fullmatch(line):
        return True
    if (
        _SUBHEADING_RE.match(line)
        or re.match(r"^\d{1,3}\.\d+[.)]?\s+", line)
        or _KNOWN_HEADING_RE.fullmatch(line)
    ):
        return True

    words = line.split()
    if len(words) <= 12 and line.isupper() and any(char.isalpha() for char in line):
        return True
    if (
        len(words) <= 10
        and not line.endswith((".", "?", "!", ";"))
        and all(word[:1].isupper() for word in words if word[:1].isalpha())
    ):
        return True

    numbered_title = re.match(r"^\d{1,2}[.)]?\s+(.+)$", line)
    if numbered_title:
        title = numbered_title.group(1)
        title_words = title.split()
        if len(title_words) <= 8 and (
            title.isupper()
            or all(word[:1].isupper() for word in title_words if word[:1].isalpha())
        ):
            return True

    return False


def _is_classification_header(line: str) -> bool:
    content = re.sub(r"^(?:header|footer)\s*:\s*", "", line, flags=re.IGNORECASE)
    return bool(_CLASSIFICATION_RE.fullmatch(content))


def _is_table_row(line: str) -> bool:
    if (
        "\t" in line
        or "|" in line
        or re.search(r"\S {3,}\S", line)
        or re.search(r"\.{2,}\s*\d{1,4}\s*$", line)
    ):
        return True
    cells = line.split()
    return len(cells) >= 4 and sum(bool(re.search(r"\d", cell)) for cell in cells) >= 3


def _is_contents_entry(line: str) -> bool:
    if _is_table_row(line):
        return True
    numbered = _MAIN_SECTION_RE.match(line)
    return bool(
        numbered
        and re.search(r"\s+\d{1,4}\s*$", numbered.group(2))
    )


def _default_paragraphs(paragraphs: list[dict]) -> list[str]:
    return [
        item["id"]
        for item in paragraphs
        if (
            item.get("section_id") in FTER_FORMAT_CONFIG["sections"]
            and FTER_FORMAT_CONFIG["sections"][item["section_id"]]["default_selected"]
        )
        or (
            item.get("section_id") not in FTER_FORMAT_CONFIG["sections"]
            and (
                item["id"] == "summary"
                or item.get("paragraph_number") in {3, 4}
            )
        )
    ]


def _fallback_paragraphs(pages: list[dict]) -> list[dict]:
    paragraphs: list[dict] = []
    ignoring_section = False
    counter = 0
    current_heading = "Document body"

    for page in pages:
        heading_lines = {
            _clean_line(line).casefold()
            for line in page.get("heading_lines", [])
        }
        blocks = re.split(r"\n\s*\n", page.get("raw_text", ""))
        for block in blocks:
            lines = [
                (raw_line, _clean_line(raw_line))
                for raw_line in block.splitlines()
            ]
            lines = [(raw_line, line) for raw_line, line in lines if line]
            body_lines: list[str] = []

            for raw_line, line in lines:
                raw_is_table_row = _is_table_row(raw_line)
                if _is_classification_header(line) or _PAGE_MARKER_RE.fullmatch(line):
                    continue
                if _IGNORED_SECTION_RE.fullmatch(line):
                    ignoring_section = True
                    continue
                if ignoring_section:
                    if _SUMMARY_RE.fullmatch(line):
                        ignoring_section = False
                    elif raw_is_table_row or _is_table_row(line):
                        continue
                    elif _is_heading(line, heading_lines):
                        current_heading = line
                        ignoring_section = False
                        continue
                    else:
                        continue
                if (
                    _SUMMARY_RE.fullmatch(line)
                    or raw_is_table_row
                    or _is_table_row(line)
                ):
                    continue
                if _is_heading(line, heading_lines):
                    current_heading = line
                    continue
                body_lines.append(line)

            text = " ".join(body_lines).strip()
            if not text:
                continue
            counter += 1
            paragraphs.append({
                "id": f"paragraph:{counter}",
                "label": f"Paragraph {counter}",
                "paragraph_number": counter,
                "page_number": page["page_number"],
                "text": text,
                "section_id": f"heading:{re.sub(r'[^a-z0-9]+', '-', current_heading.casefold()).strip('-')}",
                "section_title": current_heading,
                "parent_section_id": None,
                "parent_section_title": None,
                "is_front_matter": False,
            })

    return paragraphs


def extract_selectable_paragraphs(pages: list[dict]) -> dict:
    is_fter = _is_fter_document(pages)
    if is_fter:
        paragraphs = _extract_fter_paragraphs(pages)
        if paragraphs:
            return {
                "is_fter": True,
                "paragraphs": paragraphs,
                "default_selected_ids": _default_paragraphs(paragraphs),
            }

    paragraphs: list[dict] = []
    id_counts: defaultdict[str, int] = defaultdict(int)
    active_id: str | None = None
    active_parts: list[str] = []
    active_page = 1
    active_number: int | None = None
    ignoring_section = False
    current_heading = "Document body"
    automatic_paragraph_number = 0

    def flush() -> None:
        nonlocal active_id, active_parts, active_number
        text = " ".join(active_parts).strip()
        if active_id and text:
            id_counts[active_id] += 1
            paragraph_id = active_id
            if id_counts[active_id] > 1:
                paragraph_id = f"{active_id}:{id_counts[active_id]}"
            if active_id == "summary":
                label = "Summary"
                paragraph_number = None
                section_id = "summary"
                section_title = "Summary"
            else:
                paragraph_number = active_number
                label = (
                    f"Paragraph {paragraph_number}"
                    if paragraph_number is not None
                    else f"Paragraph {automatic_paragraph_number}"
                )
                section_id = (
                    "heading:"
                    + re.sub(
                        r"[^a-z0-9]+",
                        "-",
                        current_heading.casefold(),
                    ).strip("-")
                )
                section_title = current_heading
            paragraphs.append({
                "id": paragraph_id,
                "label": label,
                "paragraph_number": paragraph_number,
                "page_number": active_page,
                "text": text,
                "section_id": section_id,
                "section_title": section_title,
                "parent_section_id": None,
                "parent_section_title": None,
                "is_front_matter": False,
            })
        active_id = None
        active_parts = []
        active_number = None

    for page in pages:
        page_number = int(page["page_number"])
        heading_lines = {
            _clean_line(line).casefold()
            for line in page.get("heading_lines", [])
        }
        for raw_line in (page.get("raw_text") or "").splitlines():
            raw_is_table_row = _is_table_row(raw_line)
            line = _clean_line(raw_line)
            if not line:
                if active_id and active_number is None and active_id != "summary":
                    flush()
                continue
            if _is_classification_header(line) or _PAGE_MARKER_RE.fullmatch(line):
                continue

            if _IGNORED_SECTION_RE.fullmatch(line):
                flush()
                ignoring_section = True
                continue

            summary_heading = _SUMMARY_RE.fullmatch(line)
            paragraph_match = _PARAGRAPH_RE.match(line)
            if ignoring_section:
                if summary_heading:
                    ignoring_section = False
                elif raw_is_table_row or _is_table_row(line):
                    continue
                elif _is_heading(line, heading_lines):
                    ignoring_section = False
                    continue
                else:
                    continue

            if summary_heading:
                flush()
                active_id = "summary"
                active_page = page_number
                continue

            if raw_is_table_row or _is_table_row(line):
                continue

            if _is_heading(line, heading_lines):
                flush()
                current_heading = line
                continue

            if paragraph_match:
                flush()
                active_number = int(paragraph_match.group(1))
                active_id = f"paragraph:{active_number}"
                active_page = page_number
                active_parts.append(paragraph_match.group(2))
                continue

            if active_id is None:
                automatic_paragraph_number += 1
                active_id = f"paragraph:auto:{automatic_paragraph_number}"
                active_page = page_number
            active_parts.append(line)

    flush()

    if not paragraphs:
        paragraphs = _fallback_paragraphs(pages)

    return {
        "is_fter": is_fter,
        "paragraphs": paragraphs,
        "default_selected_ids": _default_paragraphs(paragraphs),
    }


def selected_paragraph_text(
    selection: dict,
    selected_ids: list[str],
) -> dict[int, str]:
    selected = set(selected_ids)
    text_by_page: defaultdict[int, list[str]] = defaultdict(list)
    for paragraph in selection["paragraphs"]:
        if paragraph["id"] in selected:
            text_by_page[paragraph["page_number"]].append(paragraph["text"])
    return {
        page_number: "\n\n".join(texts)
        for page_number, texts in text_by_page.items()
    }
