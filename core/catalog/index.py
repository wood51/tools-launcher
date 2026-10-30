"""Logique du catalogue, sans Qt : lecture des `index.json` de toutes les sources et récupération des zips."""

import json
from pathlib import Path, PurePosixPath

from core.catalog.sources import MAX_INDEX, MAX_ZIP, fetch_file, get_source, load_sources
from core.installer import TMP_DIR, installed_version, version_key
from core.registry import EXTENSION_ID, VERSION

INDEX_NAME = "index.json"
SHA256 = "0123456789abcdef"


def load_source() -> Path | None:
    """Premier dossier de catalogue actif (pour `scripts/publish.py`), sinon None."""
    for source in load_sources():
        if source["type"] == "folder" and source.get("enabled", True) and source.get("location"):
            return Path(source["location"])
    return None


def read_index(source: dict) -> list[dict]:
    """Entrées valides de l'index d'une source, marquées `source_id` et `source_name`.
    Lève OSError ou ValueError si l'index est inutilisable. La confiance repose sur la signature de chaque
    zip, vérifiée à l'installation : l'index n'est qu'une liste."""
    data = json.loads(fetch_file(source, INDEX_NAME, MAX_INDEX).decode("utf-8-sig"))
    entries = data.get("extensions") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError('clé "extensions" manquante')
    valid = []
    for entry in entries:
        try:
            entry = check_entry(entry)
        except ValueError as e:
            print(f"catalogue {source['name']} : entrée ignorée : {e}")
            continue
        entry["source_id"] = source["id"]
        entry["source_name"] = source["name"]
        valid.append(entry)
    return valid


def check_entry(entry: object) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("objet attendu")
    for key in ("id", "name", "version", "zip", "sha256"):
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"{key} manquant ou invalide")
    if not EXTENSION_ID.fullmatch(entry["id"]):
        raise ValueError(f"id invalide : {entry['id']}")
    if not VERSION.fullmatch(entry["version"]):
        raise ValueError(f"version invalide : {entry['version']}")
    if len(entry["sha256"]) != 64 or any(c not in SHA256 for c in entry["sha256"].lower()):
        raise ValueError("sha256 invalide")
    path = PurePosixPath(entry["zip"].replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in entry["zip"]:
        raise ValueError(f"chemin de zip dangereux : {entry['zip']}")
    return entry


def load_catalog() -> tuple[dict[str, list[dict]], list[str]]:
    """Entrées de toutes les sources actives, par id d'extension (la plus récente d'abord), et les erreurs
    par source. Une extension présente dans plusieurs sources garde toutes ses entrées : le choix revient
    à l'utilisateur."""
    by_id: dict[str, list[dict]] = {}
    errors = []
    for source in load_sources():
        if not source.get("enabled", True):
            continue
        try:
            entries = read_index(source)
        except (OSError, ValueError) as e:
            errors.append(f"{source.get('name', '?')} : {e}")
            continue
        for entry in entries:
            by_id.setdefault(entry["id"], []).append(entry)
    for entries in by_id.values():
        entries.sort(key=lambda e: version_key(e["version"]), reverse=True)
    return by_id, errors


def fetch_zip(entry: dict) -> Path:
    """Copie le zip de la source de l'entrée dans un fichier temporaire local (le hash est vérifié sur la copie)."""
    source = get_source(entry["source_id"])
    if source is None:
        raise ValueError("source supprimée")
    TMP_DIR.mkdir(exist_ok=True)
    local = TMP_DIR / f"{entry['id']}-{entry['version']}.zip"
    fetch_file(source, entry["zip"], MAX_ZIP, dest=local)
    return local


def is_newer(entry: dict, installed: str | None) -> bool:
    return installed is None or version_key(entry["version"]) > version_key(installed)


def find_updates() -> list[dict]:
    """Entrées les plus récentes des extensions installées pour lesquelles une version plus récente existe
    dans une source (les non installées sont ignorées). Vide si aucune source n'est lisible."""
    by_id, _errors = load_catalog()
    updates = []
    for extension_id, entries in by_id.items():
        installed = installed_version(extension_id)
        if installed is not None and is_newer(entries[0], installed):
            updates.append(entries[0])
    return updates
