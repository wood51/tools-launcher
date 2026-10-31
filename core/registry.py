import json
import os
import re
import subprocess
from pathlib import Path

from core.deps import load_failed
from core.paths import EXTENSIONS_DIR, LOG_FILE, PYTHONW, ROOT

MANIFEST_NAME = "extension.json"
BLOCKS = ("plugin", "tool", "theme")
EXTENSION_ID = re.compile(r"[a-z0-9][a-z0-9_-]*")
VERSION = re.compile(r"\d+\.\d+\.\d+")


class UnsafePathError(ValueError):
    """Un chemin du manifeste sort du dossier de l'extension."""


def check_text(data: dict, key: str, where: str = "") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}{key} manquant ou invalide")
    return value


def check_file(folder: Path, relative: str, key: str, must_exist: bool = True) -> None:
    """Le chemin doit rester dans le dossier de l'extension et, sauf mention, désigner un fichier."""
    path = folder / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(folder.resolve()):
        raise UnsafePathError(f"{key} sort du dossier de l'extension : {relative}")
    if must_exist and not path.is_file():
        raise ValueError(f"{key} introuvable : {relative}")


def load_manifest(manifest: Path) -> dict:
    """Lit et valide un `extension.json`. Lève ValueError (UnsafePathError pour un chemin dangereux)."""
    folder = manifest.parent
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ValueError(f"illisible : {e}") from e
    if not isinstance(data, dict):
        raise ValueError("le manifeste doit être un objet JSON")

    extension_id = check_text(data, "id")
    if not EXTENSION_ID.fullmatch(extension_id) or extension_id != folder.name:
        raise ValueError(f"id {extension_id!r} différent du nom du dossier {folder.name!r}")
    check_text(data, "name")
    if not VERSION.fullmatch(check_text(data, "version")):
        raise ValueError(f"version invalide (attendu 1.2.3) : {data['version']}")
    if "tooltip" in data:
        check_text(data, "tooltip")
    if "author" in data:  # simple mention ; le signataire du paquet fait foi, pas ce champ
        check_text(data, "author")
    if "category" in data:  # rangement par défaut dans le menu Outils ; l'utilisateur peut le changer
        check_text(data, "category")

    present = [block for block in BLOCKS if block in data]
    if not present:
        raise ValueError("aucun bloc plugin, tool ou theme")
    for block in present:
        if not isinstance(data[block], dict):
            raise ValueError(f"bloc {block} invalide")
        where = f"{block}."
        key = "file" if block == "theme" else "entry"
        check_file(folder, check_text(data[block], key, where), f"{where}{key}")
    if "name" in data.get("tool", {}):
        check_text(data["tool"], "name", "tool.")
    if "multiple" in data.get("tool", {}) and not isinstance(data["tool"]["multiple"], bool):
        raise ValueError("tool.multiple doit être true ou false")
    if "icon" in data.get("tool", {}):
        check_file(folder, check_text(data["tool"], "icon", "tool."), "tool.icon", must_exist=False)
    return data


def discover_extensions() -> list[dict]:
    """Manifestes valides de `extensions/` (ordre alphabétique), avec `folder` ajouté."""
    extensions = []
    if not EXTENSIONS_DIR.is_dir():
        return extensions
    failed = load_failed()
    for item in sorted(EXTENSIONS_DIR.iterdir()):
        manifest = item / MANIFEST_NAME
        if not manifest.exists():
            continue
        if item.name in failed:
            print(f"{item.name}: dépendances non installées, extension ignorée")
            continue
        try:
            data = load_manifest(manifest)
        except ValueError as e:
            print(f"{item.name}: {e}")
            continue
        data["folder"] = item
        extensions.append(data)
    return extensions


def discover_tools() -> list[dict]:
    """Les extensions qui ont un bloc `tool`, à plat : id, name, tooltip, category, entry, icon, folder."""
    return [
        {
            "id": ext["id"],
            "name": ext["tool"].get("name") or ext["name"],
            "tooltip": ext.get("tooltip", ""),
            "category": ext.get("category", "").strip(),
            "entry": ext["tool"]["entry"],
            "icon": ext["tool"].get("icon"),
            "multiple": ext["tool"].get("multiple", False),
            "folder": ext["folder"],
        }
        for ext in discover_extensions()
        if "tool" in ext
    ]


def launch_tool(tool: dict) -> subprocess.Popen:
    """Lance l'outil ; sa sortie d'erreur va dans core/data/plugins.log (pythonw cache la console)."""
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open("ab") as log_out:
        return subprocess.Popen(
            [PYTHONW, tool["folder"] / tool["entry"]],
            cwd=tool["folder"],
            env={
                **os.environ,
                "PYTHONPATH": str(ROOT),
                "PYTHONIOENCODING": "utf-8",
                "TL_EXTENSION_ID": tool["id"],
                "TL_MULTIPLE": "1" if tool.get("multiple") else "0",
            },
            stdin=subprocess.DEVNULL,
            stdout=log_out,
            stderr=log_out,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


if __name__ == "__main__":
    launch_tool(discover_tools()[0])
