from pathlib import Path

from app.services.document_extraction_service import (
    extract_document,
)
from app.services.text_normalization_service import (
    normalize_text,
)


def main() -> None:
    test_file = Path("app/FRS for Plag check Phase I(Complete).pdf")

    if not test_file.exists():
        print(
            f"Test file not found: {test_file}"
        )
        return

    pages = extract_document(test_file)

    print(
        f"Pages extracted: {len(pages)}"
    )

    for page in pages:
        normalized = normalize_text(
            page.raw_text
        )

        print()
        print("=" * 70)
        print(
            f"PAGE {page.page_number}"
        )
        print("=" * 70)

        print(
            normalized[:2000]
        )


if __name__ == "__main__":
    main()