"""Notifications Windows au nom de l'outil (et non « python »), sans dépendance.

Windows affiche le nom et l'icône enregistrés pour l'identifiant d'application (AppUserModelID)
de l'expéditeur. Chaque extension est donc enregistrée sous `Wood51.ToolsLauncher.<id>` dans
`HKCU\\Software\\Classes\\AppUserModelId` (nom affiché, icône PNG), puis la notification est
envoyée par PowerShell 5 (API Windows.UI.Notifications) avec cet identifiant. Qt n'est utilisé
que pour fabriquer l'icône PNG, à l'intérieur du lanceur.
"""

import base64
import os
import subprocess
import threading
import winreg
from pathlib import Path

from core.api import log
from core.paths import CORE_APPS, DATA_DIR, ICONS_DIR, LAUNCHER_ICON

AUMID_PREFIX = "Wood51.ToolsLauncher."
ICON_CACHE = DATA_DIR / "notify_icons"

SCRIPT = """
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$title = [Security.SecurityElement]::Escape($env:TL_TITLE)
$message = [Security.SecurityElement]::Escape($env:TL_MESSAGE)
$audio = ''
if ($env:TL_SOUND -ne '1') { $audio = '<audio silent="true"/>' }
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$title</text><text>$message</text></binding></visual>$audio</toast>")
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:TL_AUMID).Show($toast)
"""
ENCODED_SCRIPT = base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")


def aumid(extension_id: str) -> str:
    return AUMID_PREFIX + extension_id


def app_identity(extension_id: str) -> tuple[str, Path]:
    """Nom affiché et fichier d'icône (svg, png ou ico) de l'extension ; valeurs génériques sinon."""
    from core.registry import discover_extensions

    name = CORE_APPS.get(extension_id, "Tools Launcher")
    icon = LAUNCHER_ICON if extension_id in CORE_APPS or extension_id == "launcher" else ICONS_DIR / "tool.svg"
    for ext in discover_extensions():
        if ext["id"] != extension_id:
            continue
        tool = ext.get("tool", {})
        name = tool.get("name") or ext["name"]
        if tool.get("icon") and (ext["folder"] / tool["icon"]).is_file():
            icon = ext["folder"] / tool["icon"]
    return name, icon


def make_png(source: Path, destination: Path) -> bool:
    """PNG 96 px à partir d'un svg, png ou ico (nécessite Qt : à appeler dans le lanceur)."""
    from PySide6.QtGui import QIcon

    destination.parent.mkdir(parents=True, exist_ok=True)
    return QIcon(str(source)).pixmap(96, 96).save(str(destination), "PNG")


def register_app(extension_id: str) -> None:
    """Enregistre (ou met à jour) le nom et l'icône affichés pour cette extension."""
    name, icon = app_identity(extension_id)
    png = ICON_CACHE / f"{extension_id}.png"
    has_icon = make_png(icon, png)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{aumid(extension_id)}") as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, name)
        if has_icon:
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(png))


def unregister_app(extension_id: str) -> None:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{aumid(extension_id)}")
    except OSError:
        pass


def show_toast(extension_id: str, title: str, message: str, sound: bool = True) -> None:
    """Envoie la notification en tâche de fond ; un échec est écrit dans le journal."""
    try:
        register_app(extension_id)
    except OSError as e:
        log("notify", f"enregistrement de {extension_id} impossible : {e}")
    env = {
        **os.environ,
        "TL_AUMID": aumid(extension_id),
        "TL_TITLE": title,
        "TL_MESSAGE": message,
        "TL_SOUND": "1" if sound else "0",
    }

    def send() -> None:
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", ENCODED_SCRIPT],
                env=env,
                capture_output=True,
                timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                error = result.stderr.decode("utf-8", errors="replace").strip()
                log("notify", f"notification Windows refusée : {error[:300]}")
        except (OSError, subprocess.TimeoutExpired) as e:
            log("notify", f"notification Windows impossible : {e}")

    threading.Thread(target=send, daemon=True).start()


def play_sound(level: str = "info") -> None:
    """Son système associé au niveau (info, warning, error)."""
    import winsound

    winsound.MessageBeep({"warning": winsound.MB_ICONEXCLAMATION, "error": winsound.MB_ICONHAND}.get(level, winsound.MB_ICONASTERISK))
