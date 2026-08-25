"""Access to the structured candidate profile JSON."""

import json
from pathlib import Path

from app import config as settings


def load_profile() -> dict:
    path = Path(settings.PROFILE_PATH)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def has_profile() -> bool:
    return bool(load_profile())
