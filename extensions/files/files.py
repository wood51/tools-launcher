import json
import os
import shutil
import subprocess
from pathlib import Path

from core.api import get_api, write_json_atomic

FILES_CONFIG = get_api("files").data_dir / "files.json"


def check_entry(entry: dict) -> None:
    """Lève ValueError si l'entrée est invalide."""
    if not isinstance(entry, dict):
        raise ValueError("l'entrée doit être un objet JSON")
    for key in ("name", "path"):
        value = entry.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} manquant ou invalide")
    app = entry.get("app")
    if app is not None and (not isinstance(app, str) or not app):
        raise ValueError("app invalide")


def load_files() -> list[dict]:
    try:
        text = FILES_CONFIG.read_text(encoding="utf-8-sig")
        data = json.loads(text)
    except OSError:
        return []
    except ValueError:
        print(f"fichier {FILES_CONFIG} invalide")
        return []

    if not isinstance(data, dict):
        print(f"fichier {FILES_CONFIG} : objet JSON attendu")
        return []
    files = data.get("files")
    if not isinstance(files, list):
        print(f'fichier {FILES_CONFIG} : clé "files" manquante ou invalide')
        return []

    valid = []
    for entry in files:
        try:
            check_entry(entry)
        except ValueError as e:
            print(f"fichier {FILES_CONFIG} : entrée ignorée : {e}")
            continue
        valid.append(entry)
    return valid


def save_files(files: list[dict]) -> None:
    if FILES_CONFIG.exists():  # filet de sécurité : un fichier cassé lu comme vide serait écrasé
        shutil.copy2(FILES_CONFIG, FILES_CONFIG.with_suffix(".json.bak"))
    write_json_atomic(FILES_CONFIG, {"files": files})


def add_file(path: str, app: str | None = None) -> None:
    """Ajoute un fichier ; sans effet s'il est déjà dans la liste."""
    files = load_files()
    if any(entry["path"] == path for entry in files):
        return
    entry = {"name": Path(path).stem, "path": path}
    if app:
        entry["app"] = app
    files.append(entry)
    save_files(files)


def remove_file(path: str) -> None:
    save_files([entry for entry in load_files() if entry["path"] != path])


def open_file(entry: dict) -> None:
    """Ouvre avec l'application de l'entrée, sinon celle de Windows. Lève OSError en cas d'échec."""
    path = entry["path"]
    if not Path(path).exists():
        raise FileNotFoundError(f"introuvable : {path}")
    app = entry.get("app")
    if app:
        subprocess.Popen([app, path], creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        os.startfile(path)


if __name__ == "__main__":
    print(load_files())
