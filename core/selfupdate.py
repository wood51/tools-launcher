"""Mise à jour du lanceur lui-même depuis les releases GitHub publiques. Stdlib + signing.

Chaîne de confiance : le zip n'est jamais cru sur parole. `SHA256SUMS` doit porter une signature valide d'une clé de
confiance (core/assets/trusted_keys.json), et le zip téléchargé doit avoir l'empreinte listée. Seuls les fichiers du
runtime sont remplacés ; `extensions/`, `data/`, `.venv` et la configuration ne sont jamais touchés. La version
remplacée est gardée une génération dans `.launcher_backup/` (retour arrière automatique si l'écriture échoue).
"""

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from core.paths import ROOT, launcher_version
from core.registry import VERSION

REPO = "wood51/tools-launcher"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
BACKUP_DIR = ROOT / ".launcher_backup"
TMP_DIR = ROOT / ".install_tmp"
MAX_ZIP = 100_000_000
MAX_SMALL = 1_000_000
ROOT_FILES = {
    "bootstrap.pyw", "Lancer Tools Launcher.cmd", "README.md", "LICENSE",
    "requirements.txt", "VERSION", ".gitattributes", "scripts/publish.py", "scripts/sign.py",
}


class UpdateError(Exception):
    """Message destiné à l'utilisateur."""


@dataclass
class Release:
    version: str
    notes: str
    assets: dict[str, str]  # nom -> URL de téléchargement

    @property
    def zip_name(self) -> str:
        return f"ToolsLauncher-{self.version}.zip"


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def _get(url: str, limit: int, dest: Path | None = None) -> bytes:
    if not url.startswith("https://"):
        raise UpdateError("adresse non sécurisée refusée")
    request = urllib.request.Request(url, headers={"User-Agent": "ToolsLauncher-updater"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if dest is None:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise UpdateError("réponse trop volumineuse")
                return data
            size = 0
            with dest.open("wb") as f:
                while chunk := response.read(1 << 20):
                    size += len(chunk)
                    if size > limit:
                        raise UpdateError("fichier trop volumineux")
                    f.write(chunk)
            return b""
    except UpdateError:
        raise
    except OSError as e:
        raise UpdateError(f"réseau indisponible : {e}") from e


def check_latest() -> Release | None:
    """La dernière release publiée si elle est plus récente que la version installée, sinon None."""
    try:
        data = json.loads(_get(API_URL, MAX_SMALL))
        tag = str(data["tag_name"]).lstrip("v")
        if not VERSION.fullmatch(tag):
            raise ValueError(tag)
        assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
        notes = str(data.get("body") or "")
    except (ValueError, KeyError, TypeError) as e:
        raise UpdateError("réponse de GitHub illisible") from e
    try:
        current = launcher_version()
        newer = version_key(tag) > version_key(current)
    except ValueError:  # version locale inconnue ("?") : on propose la mise à jour
        newer = True
    return Release(tag, notes, assets) if newer else None


def download(release: Release) -> Path:
    """Télécharge et vérifie (signature des empreintes, puis empreinte du zip) ; renvoie le zip local."""
    from core.signing import verify_raw

    needed = (release.zip_name, "SHA256SUMS", "SHA256SUMS.sig")
    for name in needed:
        url = release.assets.get(name, "")
        if not url.startswith(DOWNLOAD_PREFIX):
            raise UpdateError(f"fichier de release manquant ou hors dépôt officiel : {name}")
    sums = _get(release.assets["SHA256SUMS"], MAX_SMALL)
    try:
        verify_raw(sums, _get(release.assets["SHA256SUMS.sig"], MAX_SMALL))
    except ValueError as e:
        raise UpdateError(f"signature de la release refusée : {e}") from e
    expected = None
    for line in sums.decode("utf-8").splitlines():
        digest, _, name = line.partition("  ")
        if name == release.zip_name:
            expected = digest.lower()
    if not expected:
        raise UpdateError("empreinte du zip absente de SHA256SUMS")
    TMP_DIR.mkdir(exist_ok=True)
    local = TMP_DIR / release.zip_name
    _get(release.assets[release.zip_name], MAX_ZIP, dest=local)
    digest = hashlib.sha256(local.read_bytes()).hexdigest()
    if digest != expected:
        local.unlink(missing_ok=True)
        raise UpdateError("empreinte du zip différente de celle signée : abandon")
    return local


def _wanted(relative: str) -> bool:
    parts = relative.split("/")
    if any(p in {"data", "__pycache__", ".git"} for p in parts) or relative.endswith(".pyc"):
        return False
    return relative in ROOT_FILES or relative.startswith("core/")


def _read_package(zip_path: Path, version: str) -> dict[str, bytes]:
    """Fichiers du runtime du zip, validés (pas de chemin qui sorte de la racine, version attendue)."""
    top = f"ToolsLauncher-{version}"
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if len(zf.infolist()) > 2000 or sum(i.file_size for i in zf.infolist()) > 200_000_000:
                raise UpdateError("archive démesurée")
            for info in zf.infolist():
                if info.is_dir():
                    continue
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in info.filename or path.parts[0] != top:
                    raise UpdateError(f"chemin dangereux dans le zip : {info.filename}")
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                if _wanted(relative):
                    files[relative] = zf.read(info)
    except zipfile.BadZipFile as e:
        raise UpdateError("zip illisible") from e
    if files.get("VERSION", b"").decode("utf-8-sig").strip() != version or "core/launcher.pyw" not in files:
        raise UpdateError("contenu du zip inattendu (VERSION ou core/launcher.pyw)")
    return files


def _current_files() -> list[str]:
    found = [str(p.relative_to(ROOT).as_posix()) for p in (ROOT / "core").rglob("*") if p.is_file()]
    found += [name for name in ROOT_FILES if (ROOT / name).is_file()]
    return sorted(n for n in found if _wanted(n))


def apply(zip_path: Path, version: str) -> None:
    """Remplace les fichiers du runtime ; revient à l'état d'avant si une écriture échoue. VERSION est écrit en dernier."""
    files = _read_package(zip_path, version)
    obsolete = [n for n in _current_files() if n not in files]
    touched = [n for n in files if (ROOT / n).is_file()] + obsolete

    shutil.rmtree(BACKUP_DIR, ignore_errors=True)
    for name in touched:
        saved = BACKUP_DIR / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, saved)
    created: list[str] = []
    try:
        for name in sorted(files, key=lambda n: n == "VERSION"):
            target = ROOT / name
            if not target.exists():
                created.append(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".upd-")
            with os.fdopen(fd, "wb") as f:
                f.write(files[name])
            os.replace(tmp, target)
        for name in obsolete:
            (ROOT / name).unlink(missing_ok=True)
    except OSError as e:
        for name in created:
            (ROOT / name).unlink(missing_ok=True)
        for name in touched:
            if (BACKUP_DIR / name).is_file():
                shutil.copy2(BACKUP_DIR / name, ROOT / name)
        raise UpdateError(f"mise à jour impossible, version précédente rétablie : {e}") from e
    finally:
        zip_path.unlink(missing_ok=True)
