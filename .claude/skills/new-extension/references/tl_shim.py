"""Repli de `core.api` pour exécuter une extension hors du lanceur Tools Launcher.

Même contrat que `get_api()` du noyau : données dans `./data`, réglages JSON atomiques,
journal sur la console et dans `data/app.log`, thème sombre embarqué. Sans lanceur,
`notify` écrit au journal et `set_badge` ne fait rien (les deux renvoient False).
À copier à côté de `main.pyw`. Dépendance : PySide6 (seulement pour apply_theme).
"""

import json
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_MAX_BYTES = 500_000

COLORS = {
    "BG": "#0f1218", "SURFACE": "#171b24", "SURFACE_2": "#1e2330",
    "BORDER": "#2a3040", "TEXT": "#e6e9ef", "MUTED": "#8b93a7",
    "ACCENT": "#4173d1", "ACCENT_HOVER": "#6a9dff", "ALT_ROW": "#1a1f2a",
    "HOVER_ROW": "#232a3a", "SELECTION": "#25407a", "SELECTION_STRONG": "#2b4a8f",
    "WARN": "#f5a524", "WARN_BG": "#3a2f12", "DROP_HOVER": "#151c2c",
    "ON_ACCENT": "#ffffff",
}

STYLESHEET = """
* { font-family: "Segoe UI"; font-size: 10pt; color: @TEXT; }
QMainWindow, QWidget#root { background: @BG; }
QLabel#title { font-size: 18pt; font-weight: 600; }
QLabel#subtitle, QLabel#muted { color: @MUTED; }
QFrame#card { background: @SURFACE; border: 1px solid @BORDER; border-radius: 10px; }
QPushButton { background: @SURFACE_2; border: 1px solid @BORDER; border-radius: 8px; padding: 8px 16px; }
QPushButton:hover { border-color: @ACCENT; }
QPushButton:disabled { color: @MUTED; }
QPushButton#primary { background: @ACCENT; border-color: @ACCENT; color: @ON_ACCENT; font-weight: 600; }
QPushButton#primary:hover { background: @ACCENT_HOVER; }
QComboBox, QLineEdit { background: @SURFACE_2; border: 1px solid @BORDER; border-radius: 6px; padding: 2px 8px; min-height: 22px; selection-background-color: @SELECTION; }
QComboBox:hover, QLineEdit:focus { border-color: @ACCENT; }
QTableWidget { background: @SURFACE; border: 1px solid @BORDER; border-radius: 10px; gridline-color: transparent; selection-background-color: @SELECTION; selection-color: @TEXT; }
QHeaderView::section { background: @SURFACE_2; color: @MUTED; border: none; padding: 8px 12px; font-weight: 600; }
QProgressBar { background: @SURFACE_2; border: none; border-radius: 2px; max-height: 4px; }
QProgressBar::chunk { background: @ACCENT; border-radius: 2px; }
QMessageBox, QDialog { background: @SURFACE; }
QToolTip { background: @SURFACE_2; color: @TEXT; border: 1px solid @BORDER; padding: 4px; }
"""


def write_json_atomic(path: Path, data: object) -> None:
    """Fichier temporaire puis `os.replace` : jamais de JSON à moitié écrit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class ExtensionAPI:
    def __init__(self, extension_id: str, data_dir: Path) -> None:
        self._id = extension_id
        self._data_dir = data_dir

    @property
    def id(self) -> str:
        return self._id

    @property
    def data_dir(self) -> Path:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        return self._data_dir

    def _path(self, name: str) -> Path:
        """`data/<name>` ; refuse tout chemin qui sortirait de `data/`."""
        base = self._data_dir.resolve()
        path = (base / name).resolve()
        if path == base or base not in path.parents:
            raise ValueError(f"nom de fichier hors de data/ : {name}")
        return path

    def load_json(self, name: str) -> object | None:
        try:
            return json.loads(self._path(name).read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            self.log(f"{name} illisible : {e}")
            return None

    def save_json(self, name: str, data: object) -> None:
        self.data_dir  # crée data/
        write_json_atomic(self._path(name), data)

    def load_settings(self) -> dict:
        data = self.load_json("settings.json")
        return data if isinstance(data, dict) else {}

    def save_settings(self, data: dict) -> None:
        self.save_json("settings.json", data)

    def log(self, message: str) -> None:
        """Console et `data/app.log`. Ne lève jamais d'exception."""
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{self._id}] {message}"
        print(line)
        try:
            log_file = self.data_dir / "app.log"
            if log_file.exists() and log_file.stat().st_size > LOG_MAX_BYTES:
                log_file.unlink()
            with log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def notify(self, title: str, message: str, level: str = "info") -> bool:
        self.log(f"notification ({level}) : {title} - {message}")
        return False

    def set_badge(self, level: str | None) -> bool:
        if level not in (None, "blue", "red"):
            raise ValueError(f"badge inconnu : {level}")
        return False

    def apply_theme(self, app) -> None:
        """Thème sombre embarqué (pas de suivi du thème du lanceur)."""
        from PySide6 import QtSvg  # noqa: F401  (sans cet import, Qt ne charge pas les icônes SVG)
        from PySide6.QtCore import Qt

        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
        # jetons entiers : @ACCENT ne doit pas toucher @ACCENT_HOVER
        app.setStyleSheet(re.sub(r"@([A-Z][A-Z0-9_]*)",lambda m: COLORS.get(m.group(1), m.group(0)), STYLESHEET))

    def launch_tool(self, extension_id: str) -> None:
        self.log(f"launch_tool indisponible hors du lanceur : {extension_id}")


def get_api(extension_id: str | None = None) -> ExtensionAPI:
    """Id donné, sinon nom du dossier du script ; données dans `<dossier du script>/data`."""
    folder = Path(sys.argv[0]).resolve().parent
    return ExtensionAPI(extension_id or folder.name, folder / "data")
