"""API commune aux outils et aux plugins : données, réglages, journal, thème, lancement.

Stdlib seulement au niveau du module (importable sans PySide6). `PluginAPI`
(core/plugin_api.py) en hérite et ajoute ce qui touche au menu du lanceur.
"""

import json
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from core.paths import CHANNEL_NAME, LOG_FILE, LOG_MAX_BYTES, extension_data_dir

ENV_EXTENSION_ID = "TL_EXTENSION_ID"  # posée par launch_tool


_crash_shown = False


def _show_error(text: str) -> None:
    """Boîte de dialogue Windows (pythonw n'a pas de console)."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, "Tools Launcher", 0x10)
    except (AttributeError, OSError):
        pass


def install_crash_handler(extension_id: str) -> None:
    """Une exception non attrapée est journalisée et montrée une fois, au lieu d'un plantage silencieux."""

    def hook(exc_type, exc, tb) -> None:
        global _crash_shown
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        log(extension_id, f"plantage :\n{details}")
        if not _crash_shown:
            _crash_shown = True
            _show_error(
                f"« {extension_id} » a rencontré une erreur :\n\n{exc_type.__name__}: {exc}"
                "\n\nDétails dans core/data/plugins.log"
            )

    sys.excepthook = hook


def write_json_atomic(path: Path, data: object) -> None:
    """Écrit dans un fichier temporaire puis le remplace d'un coup : jamais de JSON à moitié écrit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def log(extension_id: str, message: str) -> None:
    """Console et `core/data/plugins.log` (pythonw cache la console). Ne lève jamais d'exception."""
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{extension_id}] {message}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            LOG_FILE.unlink()
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def log_error(extension_id: str, error: Exception) -> None:
    log(extension_id, f"{type(error).__name__}: {error}\n{traceback.format_exc()}")


def send_message(message: dict) -> bool:
    """Envoie un message au lanceur (tube nommé). False si le lanceur ne tourne pas."""
    data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        with open("\\\\.\\pipe\\" + CHANNEL_NAME, "wb", buffering=0) as pipe:
            pipe.write(data)
        return True
    except OSError:
        return False


class ExtensionAPI:
    """L'API d'une extension. Dans un outil : `api = get_api()`."""

    def __init__(self, extension_id: str) -> None:
        self._id = extension_id

    @property
    def id(self) -> str:
        return self._id

    @property
    def data_dir(self) -> Path:
        """Dossier de données (non versionné, jamais écrasé par une mise à jour). Créé si besoin."""
        path = extension_data_dir(self._id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _path(self, name: str) -> Path:
        """`data/<name>` ; refuse tout chemin qui sortirait de `data/`."""
        base = extension_data_dir(self._id).resolve()
        path = (base / name).resolve()
        if path == base or base not in path.parents:
            raise ValueError(f"nom de fichier hors de data/ : {name}")
        return path

    def load_json(self, name: str) -> object | None:
        """Lit `data/<name>` ; None si absent ou illisible (message dans le journal)."""
        try:
            return json.loads(self._path(name).read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            self.log(f"{name} illisible : {e}")
            return None

    def save_json(self, name: str, data: object) -> None:
        """Écrit `data/<name>` de façon atomique ; `ValueError` si `name` sort de `data/`."""
        self.data_dir  # crée data/
        write_json_atomic(self._path(name), data)

    def load_settings(self) -> dict:
        data = self.load_json("settings.json")
        return data if isinstance(data, dict) else {}

    def save_settings(self, data: dict) -> None:
        self.save_json("settings.json", data)

    def log(self, message: str) -> None:
        log(self._id, message)

    def notify(self, title: str, message: str, level: str = "info") -> bool:
        """Notification du lanceur (toast). `level` : info, warning, error. False sans lanceur."""
        sent = send_message(
            {"cmd": "notify", "ext": self._id, "title": title, "message": message, "level": level}
        )
        if not sent:
            self.log(f"lanceur absent, notification perdue : {title} - {message}")
        return sent

    def set_badge(self, level: str | None) -> bool:
        """`"blue"`, `"red"` ou `None` (retire le badge de cette extension). False sans lanceur."""
        if level not in (None, "blue", "red"):
            raise ValueError(f"badge inconnu : {level}")
        return send_message({"cmd": "set_badge", "ext": self._id, "level": level})

    def open_path(self, path: str | Path) -> bool:
        """Ouvre un fichier ou un dossier avec l'association Windows."""
        target = Path(path)
        if not target.exists():
            self.log(f"chemin introuvable : {target}")
            return False
        try:
            os.startfile(str(target))
            return True
        except OSError as error:
            self.log(f"ouverture impossible : {error}")
            return False

    def open_file(self, path: str | Path) -> bool:
        """Ouvre un fichier avec l'application associée."""
        target = Path(path)
        return self.open_path(target) if target.is_file() else False

    def open_folder(self, path: str | Path) -> bool:
        """Ouvre un dossier dans l'Explorateur Windows."""
        target = Path(path)
        return self.open_path(target) if target.is_dir() else False

    def choose_file(self, parent=None, title: str = "Choisir un fichier", filter: str = "Tous les fichiers (*)") -> Path | None:
        """Affiche le sélecteur de fichier Qt et renvoie un `Path`, ou `None`."""
        from PySide6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getOpenFileName(parent, title, "", filter)
        return Path(filename) if filename else None

    def choose_folder(self, parent=None, title: str = "Choisir un dossier") -> Path | None:
        """Affiche le sélecteur de dossier Qt et renvoie un `Path`, ou `None`."""
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(parent, title)
        return Path(folder) if folder else None

    def confirm(self, parent, title: str, message: str) -> bool:
        """Demande une confirmation standard et renvoie True si l'utilisateur accepte."""
        from PySide6.QtWidgets import QMessageBox

        return QMessageBox.question(
            parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes

    def get_app_info(self) -> dict[str, str]:
        """Retourne les informations utiles au code métier sans exposer les chemins internes."""
        return {"id": self._id, "mode": "launcher" if os.environ.get(ENV_EXTENSION_ID) else "standalone"}

    def apply_theme(self, app) -> None:
        """À appeler dans un outil, après la création du `QApplication`."""
        from core.theme import apply_theme

        apply_theme(app)

    def launch_tool(self, extension_id: str) -> None:
        """Lance l'outil d'une extension d'après son `id`."""
        from core.registry import discover_tools, launch_tool

        for tool in discover_tools():
            if tool["id"] == extension_id:
                launch_tool(tool)
                return
        self.log(f"outil introuvable : {extension_id}")


def get_api(extension_id: str | None = None) -> ExtensionAPI:
    """L'API de l'extension courante : `id` donné, sinon posé par le lanceur, sinon dossier du script."""
    if extension_id is None:
        extension_id = os.environ.get(ENV_EXTENSION_ID) or Path(sys.argv[0]).resolve().parent.name
    if os.environ.get(ENV_EXTENSION_ID):  # lancé par le lanceur : pas de plantage silencieux
        install_crash_handler(extension_id)
    return ExtensionAPI(extension_id)
