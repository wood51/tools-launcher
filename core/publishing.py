"""Publication d'extensions (côté auteur) : analyse, signature d'un zip, ajout à un catalogue. Sans Qt.

Utilisé par `scripts/publish.py`, `scripts/sign.py` et l'extension « Publication ».
"""

import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from core.api import write_json_atomic
from core.installer import (
    SIGNATURE_NAME,
    InstallError,
    check_signature,
    pack_extension,
    package_digest,
    package_info,
    sha256_file,
    version_key,
)
from core.signing import sign_package, trusted_keys


@dataclass
class PackageReport:
    """Ce qu'on sait d'un zip d'extension avant de le signer ou de le publier."""

    id: str
    name: str
    version: str
    author: str
    tooltip: str
    has_requirements: bool
    signer: str  # signataire valide actuel, sinon vide
    problems: list[str]  # contrôles échoués (le zip ne s'installerait pas)


def analyse_zip(zip_path: Path) -> PackageReport:
    """Lit un zip sans rien extraire. Lève InstallError si le zip est inutilisable."""
    from core.installer import prepare_zip, discard

    try:
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as e:
        raise InstallError(f"zip illisible : {e}") from e
    with zf:
        prefix, infos, manifest = package_info(zf)
        try:
            signer = check_signature(zf, prefix, infos, manifest)
            problems = []
        except InstallError as e:
            signer, problems = "", [f"signature actuelle invalide : {e}"]
        names = {(f"{prefix}/" if prefix else "") + "requirements.txt"}
        has_requirements = bool(names & set(zf.namelist()))
    if not problems:
        try:  # mêmes contrôles complets qu'à l'installation (manifeste, chemins des blocs…)
            discard(prepare_zip(zip_path))
        except InstallError as e:
            problems.append(str(e))
    return PackageReport(
        id=manifest["id"],
        name=str(manifest.get("name", manifest["id"])),
        version=manifest["version"],
        author=str(manifest.get("author", "")),
        tooltip=str(manifest.get("tooltip", "")),
        has_requirements=has_requirements,
        signer=signer,
        problems=problems,
    )


def sign_zip(zip_in: Path, zip_out: Path, key_file: Path, key_id: str, passphrase: bytes) -> PackageReport:
    """Écrit dans `zip_out` une copie de `zip_in` avec un `SIGNATURE.json` frais. Lève InstallError ou ValueError
    (mot de passe faux). `zip_out` ne peut pas être `zip_in`."""
    if zip_out.resolve() == zip_in.resolve():
        raise ValueError("le zip signé doit être un autre fichier que l'original")
    with zipfile.ZipFile(zip_in) as zf:
        prefix, infos, manifest = package_info(zf)
        digest = package_digest(zf, prefix, infos)
        signature = sign_package(manifest["id"], manifest["version"], digest, key_file, key_id, passphrase)
        signature_name = f"{prefix}/{SIGNATURE_NAME}" if prefix else SIGNATURE_NAME
        zip_out.parent.mkdir(parents=True, exist_ok=True)
        temporary = zip_out.with_suffix(zip_out.suffix + ".part")
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as out:
                for info in infos:
                    if info.filename.replace("\\", "/") == signature_name:
                        continue
                    out.writestr(info.filename, zf.read(info))
                out.writestr(signature_name, signature)
            temporary.replace(zip_out)
        finally:
            temporary.unlink(missing_ok=True)
    return analyse_zip(zip_out)


def zip_from_folder(folder: Path, destination: Path) -> Path:
    """Zip d'un dossier d'extension (sans `data/`, caches ni ancienne signature)."""
    return pack_extension(folder, destination)


def publish_zip(catalog: Path, signed_zip: Path, notes: str = "", force: bool = False) -> dict:
    """Copie le zip (déjà signé) dans `<catalog>/zips/` et met `index.json` à jour. Lève InstallError ou ValueError.
    Une version déjà publiée ne s'écrase pas (sauf `force`), ni une version plus ancienne que la dernière."""
    report = analyse_zip(signed_zip)
    if report.problems:
        raise InstallError(report.problems[0])
    if not report.signer:
        raise InstallError("le zip n'est pas signé")
    index_path = catalog / "index.json"
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8-sig"))["extensions"]
    except FileNotFoundError:
        entries = []
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f"index.json illisible : {e}") from e
    same = [e for e in entries if e.get("id") == report.id and e.get("version") == report.version]
    if same and not force:
        raise ValueError(f"la version {report.version} est déjà publiée : changer `version` dans extension.json")
    latest = max((version_key(e["version"]) for e in entries if e.get("id") == report.id and "version" in e), default=None)
    if latest and version_key(report.version) < latest and not force:
        raise ValueError("une version plus récente est déjà publiée")
    zip_name = f"zips/{report.id}-{report.version}.zip"
    destination = catalog / zip_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(signed_zip, destination)
    entry = {
        "id": report.id,
        "name": report.name,
        "version": report.version,
        "author": report.author,
        "tooltip": report.tooltip,
        "notes": notes,
        "zip": zip_name,
        "sha256": sha256_file(destination),
    }
    entries = [e for e in entries if e not in same]
    entries.append(entry)
    write_json_atomic(index_path, {"extensions": entries})
    return entry


def key_is_trusted(key_id: str) -> bool:
    """La clé figure-t-elle dans les clés de confiance de ce lanceur (et non révoquée) ?"""
    key = trusted_keys().get(key_id)
    return key is not None and key.get("revoked") is not True
