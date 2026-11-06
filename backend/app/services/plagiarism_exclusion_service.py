from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting


EXCLUDED_WORDS_KEY = "plagiarism_excluded_words"
EXCLUDED_PHRASES_KEY = "plagiarism_excluded_phrases"


def _setting_terms(db: Session, key: str) -> list[str]:
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting is None or not setting.value:
        return []

    value = json.loads(setting.value)
    if not isinstance(value, list) or any(not isinstance(term, str) for term in value):
        raise ValueError(f"Invalid plagiarism exclusion setting: {key}")
    return [term.strip() for term in value if term.strip()]


def get_plagiarism_exclusions(db: Session) -> tuple[list[str], list[str]]:
    return (
        _setting_terms(db, EXCLUDED_WORDS_KEY),
        _setting_terms(db, EXCLUDED_PHRASES_KEY),
    )


def remove_excluded_text(
    text: str,
    words: list[str],
    phrases: list[str],
) -> str:
    terms = sorted({*words, *phrases}, key=len, reverse=True)
    for term in terms:
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()
