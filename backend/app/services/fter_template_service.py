from __future__ import annotations

import unicodedata

from sqlalchemy.orm import Session

from app.models.fter import (
    FTERTemplate,
    FTERTemplateSection,
)
from app.services.fter_template_config import FTER_TEMPLATE


def normalize_template_name(name: str) -> str:
    name = unicodedata.normalize("NFKC", name)
    return " ".join(name.lower().split())


def create_default_fter_template(
    db: Session,
    created_by=None,
):
    """
    Creates the default FTER template if it does not already exist.

    Safe to run multiple times.
    """

    existing = (
        db.query(FTERTemplate)
        .filter(
            FTERTemplate.template_name == "ASTE FTER",
            FTERTemplate.version == 1,
        )
        .first()
    )

    if existing:
        return existing

    template = FTERTemplate(
        template_name="ASTE FTER",
        version=1,
        is_active=True,
        created_by=created_by,
    )

    db.add(template)
    db.flush()

    # Map configuration objects to database objects.
    created_sections = {}

    for order, section_config in enumerate(
        FTER_TEMPLATE,
        start=1,
    ):

        parent_name = section_config.get("parent")

        parent_section = None

        if parent_name:
            parent_section = created_sections.get(
                parent_name
            )

        section = FTERTemplateSection(
            template_id=template.id,
            parent_section_id=(
                parent_section.id
                if parent_section
                else None
            ),
            section_name=section_config["name"],
            normalized_name=normalize_template_name(
                section_config["name"]
            ),
            section_order=order,
            section_level=section_config["level"],
            is_required=section_config.get(
                "required",
                False,
            ),
            is_optional=section_config.get(
                "optional",
                False,
            ),
            matching_threshold=section_config.get(
                "matching_threshold",
                0.72,
            ),
        )

        db.add(section)
        db.flush()

        created_sections[
            section_config["name"]
        ] = section

    db.commit()

    return template