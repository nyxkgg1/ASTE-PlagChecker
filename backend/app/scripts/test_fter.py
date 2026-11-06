from pathlib import Path

from app.services.document_extraction_service import (
    extract_document,
)

from app.services.fter_service import (
    validate_fter_structure,
)

from app.services.fter_template_config import (
    FTER_TEMPLATE,
)


def main():

    file_path = Path(
        "app/FRS for Plag check Phase I(Complete).pdf"
    )

    pages = extract_document(
        file_path
    )

    results = validate_fter_structure(
        pages,
        FTER_TEMPLATE,
    )

    for result in results:

        print(
            f"{result['status']:25} "
            f"{result['template_section']} "
            f"{result['confidence']:.2f}"
        )

        if result["warning"]:
            print(
                f"  WARNING: "
                f"{result['warning']}"
            )


if __name__ == "__main__":
    main()