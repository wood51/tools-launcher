"""Raccourcis Windows du lanceur : démarrage avec Windows, bureau, menu Démarrer.

Stdlib seulement. Un raccourci `Tools Launcher.lnk` vise `Lancer Tools Launcher.cmd` (réduit) : ce fichier lance
`bootstrap.pyw` avec le Python du système, ce qui permet de réparer un venv cassé. Le raccourci est créé par
PowerShell (objet WScript.Shell). Windows (ou l'entreprise) peut bloquer la création : l'erreur est remontée.
"""

import base64
import ctypes
import os
import subprocess
import uuid
from ctypes import wintypes
from pathlib import Path

from core.paths import LAUNCHER_ICON, PYTHONW, ROOT

SHORTCUT_NAME = "Tools Launcher.lnk"
FOLDERID_DESKTOP = "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"
FOLDERID_PROGRAMS = "A77F5D77-2E2B-44C3-A6A2-ABA601054A51"
SCRIPT = """
$ErrorActionPreference = 'Stop'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($env:TL_LINK)
$shortcut.TargetPath = $env:TL_TARGET
$shortcut.Arguments = $env:TL_ARGS
$shortcut.WindowStyle = 7
$shortcut.WorkingDirectory = $env:TL_WORKDIR
$shortcut.IconLocation = $env:TL_ICON
$shortcut.Description = 'Tools Launcher'
$shortcut.Save()
"""
ENCODED_SCRIPT = base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")


class _Guid(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def _known_folder(folder_id: str) -> Path:
    """Dossier Windows (bureau, programmes…) y compris redirigé, par exemple vers OneDrive."""
    guid = uuid.UUID(folder_id)
    ident = _Guid(guid.time_low, guid.time_mid, guid.time_hi_version, (ctypes.c_ubyte * 8)(*guid.bytes[8:]))
    path = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(ident), 0, None, ctypes.byref(path)) != 0:
        raise OSError("dossier Windows introuvable")
    try:
        return Path(path.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path)


def startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


#### Emplacements ####

LOCATIONS = {
    "startup": startup_dir,
    "desktop": lambda: _known_folder(FOLDERID_DESKTOP),
    "start_menu": lambda: _known_folder(FOLDERID_PROGRAMS),
}


def shortcut_path(location: str, directory: Path | None = None) -> Path:
    """Chemin du raccourci ; `directory` remplace le dossier de l'emplacement (tests)."""
    return (directory or LOCATIONS[location]()) / SHORTCUT_NAME


def is_enabled(location: str, directory: Path | None = None) -> bool:
    try:
        return shortcut_path(location, directory).is_file()
    except OSError:
        return False


def enable(location: str, directory: Path | None = None) -> None:
    """Crée le raccourci. Lève OSError s'il n'a pas pu être créé."""
    link = shortcut_path(location, directory)
    link.parent.mkdir(parents=True, exist_ok=True)
    cmd = ROOT / "Lancer Tools Launcher.cmd"
    target, arguments = (str(cmd), "") if cmd.is_file() else (str(PYTHONW), f'"{ROOT / "bootstrap.pyw"}"')
    env = {
        **os.environ,
        "TL_LINK": str(link),
        "TL_TARGET": target,
        "TL_ARGS": arguments,
        "TL_WORKDIR": str(ROOT),
        "TL_ICON": str(LAUNCHER_ICON),
    }
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", ENCODED_SCRIPT],
        env=env,
        capture_output=True,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0 or not link.is_file():
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise OSError(error[:300] or "raccourci non créé")


def disable(location: str, directory: Path | None = None) -> None:
    shortcut_path(location, directory).unlink(missing_ok=True)
