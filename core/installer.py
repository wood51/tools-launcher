"""Installation, retrait et sauvegarde des extensions (zip ou dossier). Stdlib seulement.

Principes : le zip n'est jamais extrait directement dans `extensions/` (dossier temporaire,
validation complète, puis échange) ; aucun chemin ne sort du dossier de l'extension ; `data/`
n'est jamais écrasé ; la version remplacée est gardée une génération dans `.extensions_backup/`.
"""

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from core.paths import EXTENSIONS_DIR, ROOT
from core.winnotify import unregister_app
from core.registry import EXTENSION_ID, MANIFEST_NAME, VERSION, load_manifest

TMP_DIR = ROOT / ".install_tmp"
BACKUP_DIR = ROOT / ".extensions_backup"
MAX_FILES = 2000
MAX_BYTES = 50_000_000
SKIPPED_PARTS = ("__pycache__", "__MACOSX", ".git")
SIGNATURE_NAME = "SIGNATURE.json"


class InstallError(Exception):
    """Message destiné à l'utilisateur."""


@dataclass
class Prepared:
    """Extension validée, extraite dans un dossier temporaire, prête à être installée."""

    id: str
    name: str
    version: str
    blocks: list[str]
    has_requirements: bool
    previous_version: str | None
    folder: Path  # dossier temporaire de l'extension
    work_dir: Path  # à supprimer après coup
    signer: str = ""  # nom du signataire si la signature est valide, sinon vide


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def installed_version(extension_id: str) -> str | None:
    try:
        data = json.loads((EXTENSIONS_DIR / extension_id / MANIFEST_NAME).read_text(encoding="utf-8-sig"))
        version = data.get("version")
        return version if isinstance(version, str) else None
    except (OSError, ValueError):
        return None


#### Lecture sûre d'un zip ####


def _clean_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ":" in name or ".." in path.parts:
        raise InstallError(f"chemin dangereux dans le zip : {name}")
    return path


def _layout(zf: zipfile.ZipFile) -> tuple[str, list[zipfile.ZipInfo]]:
    """Préfixe commun (« » ou « dossier/ ») et fichiers utiles. Le manifeste est à la racine ou un niveau plus bas."""
    infos = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        path = _clean_name(info.filename)
        if any(part in SKIPPED_PARTS for part in path.parts):
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            raise InstallError(f"lien symbolique refusé : {info.filename}")
        infos.append((path, info))
    if len(infos) > MAX_FILES:
        raise InstallError(f"trop de fichiers (plus de {MAX_FILES})")
    manifests = [p for p, _ in infos if p.name == MANIFEST_NAME and len(p.parts) <= 2]
    if len(manifests) != 1:
        raise InstallError(f"le zip doit contenir un seul {MANIFEST_NAME} (à la racine ou dans un dossier)")
    prefix = manifests[0].parts[:-1]
    outside = [p for p, _ in infos if p.parts[: len(prefix)] != prefix]
    if outside:
        raise InstallError(f"fichiers hors du dossier de l'extension : {outside[0]}")
    return "/".join(prefix), [info for _, info in infos]


def package_info(zf: zipfile.ZipFile) -> tuple[str, list[zipfile.ZipInfo], dict]:
    """Préfixe, fichiers utiles et manifeste (id et version valides) d'un zip d'extension."""
    prefix, infos = _layout(zf)
    manifest_name = f"{prefix}/{MANIFEST_NAME}" if prefix else MANIFEST_NAME
    try:
        manifest = json.loads(zf.read(manifest_name).decode("utf-8-sig"))
        extension_id, version = manifest.get("id"), manifest.get("version")
    except (ValueError, AttributeError) as e:
        raise InstallError(f"{MANIFEST_NAME} invalide : {e}") from e
    if not isinstance(extension_id, str) or not EXTENSION_ID.fullmatch(extension_id):
        raise InstallError("identifiant d'extension invalide")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise InstallError("version invalide")
    return prefix, infos, manifest


def package_digest(zf: zipfile.ZipFile, prefix: str, infos: list[zipfile.ZipInfo]) -> str:
    """Empreinte de tous les fichiers du paquet (chemin et contenu), hors `SIGNATURE.json`."""
    records = []
    total = 0
    for info in infos:
        relative = _clean_name(info.filename)
        relative = relative.relative_to(prefix) if prefix else relative
        if relative.as_posix() == SIGNATURE_NAME:
            continue
        digest = hashlib.sha256()
        with zf.open(info) as source:
            for chunk in iter(lambda: source.read(1 << 16), b""):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise InstallError(f"contenu trop gros (plus de {MAX_BYTES // 1_000_000} Mo)")
                digest.update(chunk)
        records.append(f"{relative.as_posix()}\0{digest.hexdigest()}\n")
    return hashlib.sha256("".join(sorted(records)).encode("utf-8")).hexdigest()


def check_signature(zf: zipfile.ZipFile, prefix: str, infos: list[zipfile.ZipInfo], manifest: dict) -> str:
    """Nom du signataire si `SIGNATURE.json` est présent et valide, chaîne vide s'il est absent.
    Une signature présente mais invalide lève InstallError."""
    name = f"{prefix}/{SIGNATURE_NAME}" if prefix else SIGNATURE_NAME
    if name not in zf.namelist():
        return ""
    from core.signing import verify_package

    try:
        return verify_package(manifest["id"], manifest["version"], package_digest(zf, prefix, infos), zf.read(name))
    except ImportError:
        raise InstallError("paquet cryptography manquant : relancez bootstrap.pyw") from None
    except ValueError as e:
        raise InstallError(str(e)) from e


def prepare_zip(zip_path: Path, expected_sha256: str | None = None, require_signature: bool = False) -> Prepared:
    """Vérifie le hash et la signature, valide et extrait dans un dossier temporaire. Rien n'est installé.
    Une signature présente doit être valide ; `require_signature` refuse aussi un zip non signé."""
    if expected_sha256 and sha256_file(zip_path) != expected_sha256.lower():
        raise InstallError("empreinte SHA-256 différente de celle du catalogue : zip refusé")
    TMP_DIR.mkdir(exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(dir=TMP_DIR))
    try:
        try:
            zf = zipfile.ZipFile(zip_path)
        except (OSError, zipfile.BadZipFile) as e:
            raise InstallError(f"zip illisible : {e}") from e
        with zf:
            prefix, infos, manifest_data = package_info(zf)
            signer = check_signature(zf, prefix, infos, manifest_data)
            if require_signature and not signer:
                raise InstallError("extension non signée : refusée par cette source")
            extension_id = manifest_data["id"]
            folder = work_dir / extension_id
            total = 0
            for info in infos:
                relative = _clean_name(info.filename).relative_to(prefix) if prefix else _clean_name(info.filename)
                if relative.parts[0] == "data":  # jamais de données livrées dans un zip
                    continue
                destination = folder.joinpath(*relative.parts)
                if not destination.resolve().is_relative_to(folder.resolve()):
                    raise InstallError(f"chemin dangereux dans le zip : {info.filename}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as source, destination.open("wb") as target:
                    for chunk in iter(lambda: source.read(1 << 16), b""):
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise InstallError(f"contenu trop gros (plus de {MAX_BYTES // 1_000_000} Mo)")
                        target.write(chunk)
        try:
            manifest = load_manifest(folder / MANIFEST_NAME)
        except ValueError as e:
            raise InstallError(f"extension invalide : {e}") from e
        return Prepared(
            id=manifest["id"],
            name=manifest["name"],
            version=manifest["version"],
            blocks=[b for b in ("tool", "plugin", "theme") if b in manifest],
            has_requirements=(folder / "requirements.txt").is_file(),
            previous_version=installed_version(manifest["id"]),
            folder=folder,
            work_dir=work_dir,
            signer=signer,
        )
    except BaseException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def prepare_folder(folder: Path) -> Prepared:
    """Un dossier d'extension passe par un zip temporaire : mêmes contrôles que pour un zip."""
    TMP_DIR.mkdir(exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(dir=TMP_DIR))
    try:
        archive = pack_extension(folder, work_dir / "pack.zip")
        return prepare_zip(archive)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def discard(prepared: Prepared) -> None:
    shutil.rmtree(prepared.work_dir, ignore_errors=True)


#### Installation, retrait, retour arrière ####


def commit(prepared: Prepared) -> None:
    """Échange l'ancienne version (gardée dans .extensions_backup) contre la nouvelle ; `data/` suit."""
    target = EXTENSIONS_DIR / prepared.id
    backup = BACKUP_DIR / prepared.id
    EXTENSIONS_DIR.mkdir(exist_ok=True)
    try:
        if target.exists():
            BACKUP_DIR.mkdir(exist_ok=True)
            shutil.rmtree(backup, ignore_errors=True)
            try:
                os.replace(target, backup)
            except OSError as e:
                raise InstallError("l'extension est ouverte : fermez-la d'abord") from e
            try:
                if (backup / "data").is_dir():
                    shutil.move(str(backup / "data"), str(prepared.folder / "data"))
                os.replace(prepared.folder, target)
            except OSError as e:
                if (prepared.folder / "data").is_dir():
                    shutil.move(str(prepared.folder / "data"), str(backup / "data"))
                os.replace(backup, target)  # retour à l'état d'avant
                raise InstallError(f"installation impossible : {e}") from e
        else:
            os.replace(prepared.folder, target)
    finally:
        shutil.rmtree(prepared.work_dir, ignore_errors=True)


def uninstall(extension_id: str, keep_data: bool) -> None:
    if not EXTENSION_ID.fullmatch(extension_id):
        raise InstallError("identifiant invalide")
    target = EXTENSIONS_DIR / extension_id
    if not target.is_dir():
        raise InstallError("extension introuvable")
    backup = BACKUP_DIR / extension_id
    BACKUP_DIR.mkdir(exist_ok=True)
    shutil.rmtree(backup, ignore_errors=True)
    try:
        os.replace(target, backup)
    except OSError as e:
        raise InstallError("l'extension est ouverte : fermez-la d'abord") from e
    if (backup / "data").is_dir():
        if keep_data:  # le dossier reste, sans manifeste : ignoré par le lanceur, repris à la réinstallation
            target.mkdir()
            shutil.move(str(backup / "data"), str(target / "data"))
        else:
            shutil.rmtree(backup / "data", ignore_errors=True)
    unregister_app(extension_id)  # nom d'expéditeur des notifications Windows


def backup_version(extension_id: str) -> str | None:
    """Version de la sauvegarde (retour arrière possible), sinon None."""
    try:
        data = json.loads((BACKUP_DIR / extension_id / MANIFEST_NAME).read_text(encoding="utf-8-sig"))
        return data.get("version") if isinstance(data.get("version"), str) else None
    except (OSError, ValueError):
        return None


def restore_backup(extension_id: str) -> None:
    """Remet la version précédente ; la version actuelle devient la sauvegarde. `data/` reste en place."""
    if backup_version(extension_id) is None:
        raise InstallError("aucune sauvegarde")
    target = EXTENSIONS_DIR / extension_id
    backup = BACKUP_DIR / extension_id
    swap = BACKUP_DIR / (extension_id + ".swap")
    shutil.rmtree(swap, ignore_errors=True)
    try:
        if target.exists():
            os.replace(target, swap)
        os.replace(backup, target)
    except OSError as e:
        if swap.exists() and not target.exists():
            os.replace(swap, target)
        raise InstallError("l'extension est ouverte : fermez-la d'abord") from e
    if (swap / "data").is_dir():
        shutil.rmtree(target / "data", ignore_errors=True)
        shutil.move(str(swap / "data"), str(target / "data"))
    if swap.exists():
        os.replace(swap, backup)


#### Fabrication d'un zip ####


def pack_extension(folder: Path, destination: Path) -> Path:
    """Zip d'une extension (manifeste à la racine), sans `data/` ni caches."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder)
            if not path.is_file() or path.is_symlink() or relative.parts[0] == "data":
                continue
            if any(part in SKIPPED_PARTS for part in relative.parts) or path.suffix == ".pyc":
                continue
            if relative.as_posix() == SIGNATURE_NAME:  # le contenu a pu changer : à signer de nouveau
                continue
            zf.write(path, relative.as_posix())
    return destination
