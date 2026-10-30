"""Démarrage automatique avec Windows : un raccourci (Python du venv + `bootstrap.pyw`) dans le dossier de démarrage.

Stdlib seulement. Le raccourci est créé par PowerShell (objet WScript.Shell). Windows (ou l'entreprise)
peut bloquer le démarrage automatique : dans ce cas la création échoue et l'erreur est remontée.
"""

import base64
import os
import subprocess
from pathlib import Path

from core.paths import LAUNCHER_ICON, PYTHONW, ROOT

SHORTCUT_NAME = "Tools Launcher.lnk"
SCRIPT = """
$ErrorActionPreference = 'Stop'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($env:TL_LINK)
$shortcut.TargetPath = $env:TL_TARGET
$shortcut.Arguments = $env:TL_ARGS
$shortcut.WorkingDirectory = $env:TL_WORKDIR
$shortcut.IconLocation = $env:TL_ICON
$shortcut.Description = 'Tools Launcher'
$shortcut.Save()
"""
ENCODED_SCRIPT = base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")


def startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path(directory: Path | None = None) -> Path:
    return (directory or startup_dir()) / SHORTCUT_NAME


def is_enabled(directory: Path | None = None) -> bool:
    return shortcut_path(directory).is_file()


def enable(directory: Path | None = None) -> None:
    """Crée le raccourci. Lève OSError s'il n'a pas pu être créé."""
    link = shortcut_path(directory)
    link.parent.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "TL_LINK": str(link),
        # le Python du venv lance bootstrap.pyw : pas besoin que .pyw soit associé à Python (zip autonome)
        "TL_TARGET": str(PYTHONW),
        "TL_ARGS": f'"{ROOT / "bootstrap.pyw"}"',
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


def disable(directory: Path | None = None) -> None:
    shortcut_path(directory).unlink(missing_ok=True)
