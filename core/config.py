"""Configuration du lanceur : un seul fichier, `core/data/config.json`, une section par sujet.

Stdlib seulement. Lecture tolérante (fichier absent ou invalide : valeurs par défaut) ;
l'écriture est atomique. Sections actuelles : `plugins` (clé `disabled`).
"""

import json

from core.api import write_json_atomic
from core.paths import CONFIG_FILE


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config: dict) -> None:
    write_json_atomic(CONFIG_FILE, config)


def get_section(name: str) -> dict:
    section = load_config().get(name)
    return section if isinstance(section, dict) else {}


def set_section(name: str, values: dict) -> None:
    """Remplace une section en gardant les autres telles quelles."""
    config = load_config()
    config[name] = values
    save_config(config)
