"""Sources du catalogue (dossier ou dépôt Git) : stockage, jetons chiffrés, lecture de fichiers.

Sans Qt (dulwich n'est importé qu'à l'usage : le bootstrap n'en dépend pas). Chaque source sert le même `index.json` et les mêmes zips ; seul le moyen de les
récupérer change. Un dépôt Git est récupéré (superficiellement, sans copie de travail) dans
`core/data/catalog_git/<id>` avec dulwich, sans `git.exe`. Les jetons sont chiffrés avec DPAPI (liés à la session
Windows) et jamais écrits en clair ni dans les messages d'erreur.
"""

import base64
import ctypes
import json
import shutil
import urllib.parse
import uuid
from ctypes import wintypes
from pathlib import Path

from core.api import write_json_atomic
from core.paths import DATA_DIR

SETTINGS_FILE = DATA_DIR / "catalog.json"
GIT_CACHE_DIR = DATA_DIR / "catalog_git"
SOURCE_TYPES = {
    "folder": "Dossier ou partage",
    "git": "Dépôt Git",
}
MAX_INDEX = 2_000_000
MAX_ZIP = 100_000_000
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


#### Jetons chiffrés (DPAPI) ####


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = _Blob()
    crypt32 = ctypes.windll.crypt32
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not function(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("chiffrement du jeton impossible (DPAPI)")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def encrypt_token(token: str) -> str:
    return base64.b64encode(_dpapi(token.encode("utf-8"), True)).decode("ascii")


def get_token(source: dict) -> str:
    """Jeton en clair, ou chaîne vide s'il n'y en a pas ou s'il ne se déchiffre plus (autre session Windows)."""
    value = source.get("token")
    if not isinstance(value, str) or not value:
        return ""
    try:
        return _dpapi(base64.b64decode(value), False).decode("utf-8")
    except (OSError, ValueError):
        return ""


#### Liste des sources ####


def _read_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def new_source(**fields) -> dict:
    return {"id": uuid.uuid4().hex[:8], "enabled": True, **fields}


def load_sources() -> list[dict]:
    """Sources enregistrées. L'ancien réglage `source` (un seul dossier) est repris comme première source."""
    data = _read_settings()
    sources = data.get("sources")
    if isinstance(sources, list):
        return [s for s in sources if isinstance(s, dict) and s.get("id") and s.get("type") in SOURCE_TYPES]
    legacy = data.get("source")
    if isinstance(legacy, str) and legacy:
        return [new_source(name="Catalogue", type="folder", location=legacy)]
    return []


def save_sources(sources: list[dict]) -> None:
    data = _read_settings()
    data.pop("source", None)
    data["sources"] = sources
    write_json_atomic(SETTINGS_FILE, data)


def get_source(source_id: str) -> dict | None:
    return next((s for s in load_sources() if s["id"] == source_id), None)


def validate_source(source: dict) -> None:
    """Lève ValueError (message pour l'utilisateur) si la source est inutilisable."""
    if not str(source.get("name", "")).strip():
        raise ValueError("le nom est obligatoire")
    kind = source.get("type")
    location = str(source.get("location", "")).strip()
    if kind not in SOURCE_TYPES:
        raise ValueError("type de source inconnu")
    if not location:
        raise ValueError("l'emplacement est obligatoire")
    if kind == "git":
        _check_git_location(location)
        ref = str(source.get("ref", "")).strip()
        if ref.startswith("-") or any(c.isspace() for c in ref):
            raise ValueError("branche invalide")
    sub = str(source.get("path", "")).replace("\\", "/")
    if ".." in sub.split("/") or sub.startswith("/") or ":" in sub:
        raise ValueError("sous-dossier invalide")


def _check_git_location(location: str) -> None:
    if location.startswith("-"):
        raise ValueError("adresse invalide")
    if "://" in location:
        parts = urllib.parse.urlsplit(location)
        secure = parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS)
        if not (parts.hostname and secure):
            raise ValueError("l'adresse du dépôt doit commencer par https://")
    elif not Path(location).exists():
        raise ValueError("adresse https:// ou dossier de dépôt local attendu")


#### Git (dulwich, sans git.exe) ####

CATALOG_REF = b"refs/heads/catalog"  # le commit de la source, mémorisé dans le dépôt local


def _wanted_sha(refs: dict, ref: str) -> bytes:
    names = [f"refs/heads/{ref}".encode(), f"refs/tags/{ref}".encode()] if ref else [b"HEAD"]
    for name in names:
        if name in refs:
            return refs[name]
    raise ValueError(f"branche ou étiquette introuvable : {ref}")


def sync_git(source: dict) -> Path:
    """Met à jour (ou crée) le dépôt local de la source (sans copie de travail) et renvoie son dossier."""
    from dulwich.config import ConfigDict
    from dulwich.client import get_transport_and_path
    from dulwich.repo import Repo

    folder = GIT_CACHE_DIR / source["id"]
    url = str(source["location"]).strip()
    ref = str(source.get("ref", "")).strip()
    remote = "://" in url
    token = get_token(source)
    credentials = {"username": "token", "password": token} if token and remote else {}
    picked = {}
    repo = Repo(str(folder)) if (folder / "HEAD").is_file() else Repo.init_bare(str(folder), mkdir=True)
    try:

        def determine_wants(refs, depth=None):
            picked["sha"] = _wanted_sha(refs, ref)
            return [] if picked["sha"] in repo.object_store else [picked["sha"]]

        try:
            client, path = get_transport_and_path(url, config=ConfigDict(), **credentials)
            client.fetch(path, repo, determine_wants=determine_wants, depth=1 if remote else None)
        except ValueError:
            raise
        except Exception as e:
            message = str(e).replace(token, "***") if token else str(e)
            denied = type(e).__name__ in ("HTTPUnauthorized", "HTTPForbidden")
            raise ValueError(f"git : {message or type(e).__name__}" + (" (jeton absent, expiré ou sans droit ?)" if denied else "")) from None
        repo.refs[CATALOG_REF] = picked["sha"]
    finally:
        repo.close()
    return folder


def remove_git_cache(source_id: str) -> None:
    shutil.rmtree(GIT_CACHE_DIR / source_id, ignore_errors=True)


def _read_git(source: dict, relative: str, limit: int, dest: Path | None) -> bytes:
    from dulwich.objects import Blob, Tag
    from dulwich.object_store import tree_lookup_path
    from dulwich.repo import Repo

    sub = str(source.get("path", "")).replace("\\", "/").strip("/")
    path = f"{sub}/{relative}" if sub else relative
    repo = Repo(str(GIT_CACHE_DIR / source["id"]))
    try:
        obj = repo[repo.refs[CATALOG_REF]]
        while isinstance(obj, Tag):
            obj = repo[obj.object[1]]
        try:
            _mode, sha = tree_lookup_path(repo.__getitem__, obj.tree, path.encode("utf-8"))
        except KeyError:
            raise ValueError(f"fichier introuvable dans le dépôt : {path}") from None
        blob = repo[sha]
        if not isinstance(blob, Blob):
            raise ValueError(f"pas un fichier : {path}")
        if blob.raw_length() > limit:
            raise ValueError(f"fichier trop gros (plus de {limit // 1_000_000} Mo)")
        data = blob.data
    finally:
        repo.close()
    if dest:
        dest.write_bytes(data)
        return b""
    return data


#### Lecture des fichiers ####


def _read_local(root: Path, relative: str, limit: int, dest: Path | None) -> bytes:
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("fichier hors du catalogue")
    if path.stat().st_size > limit:
        raise ValueError(f"fichier trop gros (plus de {limit // 1_000_000} Mo)")
    if dest:
        shutil.copyfile(path, dest)
        return b""
    return path.read_bytes()


def fetch_file(source: dict, relative: str, limit: int, dest: Path | None = None) -> bytes:
    """Contenu du fichier `relative` de la source (ou écrit dans `dest`, et alors b""). Lève OSError ou ValueError.
    Pour un dépôt Git, lire `index.json` met d'abord le dépôt local à jour ; les zips sont lus dans ce dépôt."""
    relative = relative.replace("\\", "/")
    if source["type"] == "folder":
        return _read_local(Path(source["location"]), relative, limit, dest)
    if relative == "index.json" or not (GIT_CACHE_DIR / source["id"] / "HEAD").is_file():
        sync_git(source)
    return _read_git(source, relative, limit, dest)
