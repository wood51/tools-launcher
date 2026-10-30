"""Démarrage automatique avec Windows : un raccourci dans le dossier de démarrage (voir `core/shortcuts.py`).

Stdlib seulement. Windows (ou l'entreprise) peut bloquer le démarrage automatique : dans ce cas la création
échoue et l'erreur est remontée.
"""

from pathlib import Path

from core import shortcuts
from core.shortcuts import SHORTCUT_NAME, startup_dir  # noqa: F401  (noms historiques)


def shortcut_path(directory: Path | None = None) -> Path:
    return shortcuts.shortcut_path("startup", directory)


def is_enabled(directory: Path | None = None) -> bool:
    return shortcuts.is_enabled("startup", directory)


def enable(directory: Path | None = None) -> None:
    """Crée le raccourci. Lève OSError s'il n'a pas pu être créé."""
    shortcuts.enable("startup", directory)


def disable(directory: Path | None = None) -> None:
    shortcuts.disable("startup", directory)
