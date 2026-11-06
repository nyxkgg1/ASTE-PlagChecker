from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.fter import (
    FTERSectionResult,
    FTERTemplateSection,
    FTERValidationResult,
)
from app.models.scan import ScanSection


def save_fter_results(
    db: Session,
    *,
    scan_id,
    template_id,
    validation_results: list[dict],
):

    # ---------------------------------------------------------
    # Create validation record
    # ---------------------------------------------------------

    warning_statuses = {
        "MISSING_WARNING",
        "POSSIBLE_MISMATCH",
        "POSSIBLE_ORDER_MISMATCH",
    }

    info_statuses = {
        "OPTIONAL_NOT_PRESENT",
        "ADDITIONAL",
    }

    warning_count = sum(
        1
        for result in validation_results
        if result["status"] in warning_statuses
    )

    info_count = sum(
        1
        for result in validation_results
        if result["status"] in info_statuses
    )

    validation = FTERValidationResult(
        scan_id=scan_id,
        template_id=template_id,
        warning_count=warning_count,
        info_count=info_count,
    )

    db.add(validation)
    db.flush()

    # ---------------------------------------------------------
    # Load template sections
    # ---------------------------------------------------------

    template_sections = (
        db.query(FTERTemplateSection)
        .filter(
            FTERTemplateSection.template_id
            == template_id
        )
        .all()
    )

    template_section_map = {
        section.section_name: section
        for section in template_sections
    }

    # ---------------------------------------------------------
    # Create ScanSection records
    # ---------------------------------------------------------

    detected_section_map = {}

    for result in validation_results:

        detected_title = result.get(
            "detected_title"
        )

        if not detected_title:
            continue

        scan_section = ScanSection(
            scan_id=scan_id,
            section_title=detected_title,
            normalized_title=(
                detected_title.lower().strip()
            ),
            section_level=result["level"],
            section_order=result["section_order"],
            page_start=result["page_number"],
            page_end=result["page_number"],
            detection_confidence=result["confidence"],
        )

        db.add(scan_section)

        template_name = result.get(
            "template_section"
        )

        if template_name:
            detected_section_map[
                template_name
            ] = scan_section

    db.flush()

    # ---------------------------------------------------------
    # Create FTER section results
    # ---------------------------------------------------------

    for result in validation_results:

        template_name = result.get(
            "template_section"
        )

        template_section = (
            template_section_map.get(
                template_name
            )
            if template_name
            else None
        )

        # Additional/unrecognized headings do not have
        # a template section.
        if template_section is None:

            if result["status"] != "ADDITIONAL":
                continue

            # There is no valid template_section_id for
            # an additional heading, so don't insert it
            # into fter_section_results.
            continue

        detected_section = (
            detected_section_map.get(
                template_name
            )
        )

        section_result = FTERSectionResult(
            validation_id=validation.id,
            template_section_id=template_section.id,
            detected_section_id=(
                detected_section.id
                if detected_section
                else None
            ),
            detection_status=result["status"],
            confidence=result["confidence"],
            warning_message=result["warning"],
        )

        db.add(section_result)

    db.commit()

    return validation