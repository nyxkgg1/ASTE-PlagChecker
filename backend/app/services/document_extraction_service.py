from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from docx import Document
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph


@dataclass
class ExtractedPage:
    page_number: int
    raw_text: str
    heading_lines: list[str] = field(default_factory=list)


def _format_table_rows(rows: list[list[str]]) -> str:
    return "\n".join(
        "| " + " | ".join(
            cell.replace("|", r"\|").replace("\n", " ").strip()
            for cell in row
        ) + " |"
        for row in rows
    )


def extract_pdf(file_path: Path) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []

    with pymupdf.open(file_path) as document:
        for index, page in enumerate(document):
            text = page.get_text("text", sort=True)
            tables = page.find_tables().tables
            if tables:
                table_bounds = [table.bbox for table in tables]
                page_blocks: list[tuple[float, float, str]] = []
                for block in page.get_text("blocks"):
                    if len(block) < 5 or not isinstance(block[4], str):
                        continue
                    x0, y0, x1, y1 = block[:4]
                    center_x = (x0 + x1) / 2
                    center_y = (y0 + y1) / 2
                    if any(
                        bounds[0] <= center_x <= bounds[2]
                        and bounds[1] <= center_y <= bounds[3]
                        for bounds in table_bounds
                    ):
                        continue
                    block_text = block[4].strip()
                    if block_text:
                        page_blocks.append((y0, x0, block_text))

                for table in tables:
                    table_rows = [
                        [str(cell or "") for cell in row]
                        for row in table.extract()
                    ]
                    table_text = _format_table_rows(table_rows)
                    if table_text:
                        page_blocks.append(
                            (table.bbox[1], table.bbox[0], table_text)
                        )

                page_blocks.sort(key=lambda item: (item[0], item[1]))
                text = "\n\n".join(
                    block_text for _, _, block_text in page_blocks
                )

            pages.append(
                ExtractedPage(
                    page_number=index + 1,
                    raw_text=text,
                )
            )

    return pages


def extract_docx(file_path: Path) -> list[ExtractedPage]:
    document = Document(file_path)

    content_blocks: list[str] = []
    heading_lines = []

    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            style_name = item.style.name.casefold() if item.style else ""
            if style_name.startswith("heading") or style_name in {"title", "subtitle"}:
                heading_lines.append(text)
            content_blocks.append(text)
        elif isinstance(item, DocxTable):
            rows = [
                [cell.text.strip() for cell in row.cells]
                for row in item.rows
            ]
            table_text = _format_table_rows(rows)
            if table_text:
                content_blocks.append(table_text)

    # DOCX does not naturally provide PDF-style pages.
    # For the first version, treat the complete document
    # as one logical page.
    combined_text = "\n\n".join(content_blocks)

    return [
        ExtractedPage(
            page_number=1,
            raw_text=combined_text,
            heading_lines=heading_lines,
        )
    ]


def extract_txt(file_path: Path) -> list[ExtractedPage]:
    text = file_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    return [
        ExtractedPage(
            page_number=1,
            raw_text=text,
        )
    ]


def extract_document(
    file_path: str | Path,
) -> list[ExtractedPage]:

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {path}"
        )

    extension = path.suffix.lower()

    if extension == ".pdf":
        return extract_pdf(path)

    if extension == ".docx":
        return extract_docx(path)

    if extension == ".txt":
        return extract_txt(path)

    raise ValueError(
        "Unsupported document type. "
        "Supported types: PDF, DOCX, TXT."
    )