from __future__ import annotations

from app.services.fter_matching_service import (
    detect_headings,
    match_heading,
)


def validate_fter_structure(
    pages,
    template_sections,
):

    detected_headings = detect_headings(pages)

    results = []

    matched_template_names = set()

    detected_section_counter = 0

    # ---------------------------------------------------------
    # STEP 1: Match detected headings
    # ---------------------------------------------------------

    for heading in detected_headings:

        detected_section_counter += 1

        matched_section, confidence = match_heading(
            heading["title"],
            template_sections,
        )

        if matched_section is None:

            results.append(
                {
                    "detected_title": heading["title"],
                    "page_number": heading["page_number"],
                    "level": heading["level"],
                    "section_order": detected_section_counter,
                    "status": "ADDITIONAL",
                    "confidence": confidence,
                    "warning": (
                        "Additional or unrecognized "
                        "section detected."
                    ),
                    "template_section": None,
                }
            )

            continue

        template_name = matched_section["name"]

        # -----------------------------------------------------
        # Duplicate section detection
        # -----------------------------------------------------

        if template_name in matched_template_names:

            results.append(
                {
                    "detected_title": heading["title"],
                    "page_number": heading["page_number"],
                    "level": heading["level"],
                    "section_order": detected_section_counter,
                    "status": "POSSIBLE_MISMATCH",
                    "confidence": confidence,
                    "warning": (
                        f"Section '{template_name}' "
                        "appears more than once."
                    ),
                    "template_section": template_name,
                }
            )

            continue

        matched_template_names.add(template_name)

        results.append(
            {
                "detected_title": heading["title"],
                "page_number": heading["page_number"],
                "level": heading["level"],
                "section_order": detected_section_counter,
                "status": "PRESENT",
                "confidence": confidence,
                "warning": None,
                "template_section": template_name,
            }
        )

    # ---------------------------------------------------------
    # STEP 2: Missing sections
    # ---------------------------------------------------------

    for section in template_sections:

        section_name = section["name"]

        if section_name in matched_template_names:
            continue

        if section.get("optional"):

            results.append(
                {
                    "detected_title": None,
                    "page_number": None,
                    "level": section["level"],
                    "section_order": None,
                    "status": "OPTIONAL_NOT_PRESENT",
                    "confidence": 1.0,
                    "warning": (
                        f"Optional section "
                        f"'{section_name}' "
                        "was not detected."
                    ),
                    "template_section": section_name,
                }
            )

        elif section.get("required"):

            results.append(
                {
                    "detected_title": None,
                    "page_number": None,
                    "level": section["level"],
                    "section_order": None,
                    "status": "MISSING_WARNING",
                    "confidence": 1.0,
                    "warning": (
                        f"Required section "
                        f"'{section_name}' "
                        "was not detected."
                    ),
                    "template_section": section_name,
                }
            )

    # ---------------------------------------------------------
    # STEP 3: Order validation
    # ---------------------------------------------------------

    template_order = {
        section["name"]: index
        for index, section
        in enumerate(template_sections)
    }

    matched_results = [
        result
        for result in results
        if (
            result["status"] == "PRESENT"
            and result["template_section"] is not None
        )
    ]

    previous_template_position = -1

    for result in matched_results:

        current_position = template_order[
            result["template_section"]
        ]

        if current_position < previous_template_position:

            result["status"] = (
                "POSSIBLE_ORDER_MISMATCH"
            )

            result["warning"] = (
                f"Section '{result['template_section']}' "
                "appears out of the expected order."
            )

        previous_template_position = max(
            previous_template_position,
            current_position,
        )

    return results