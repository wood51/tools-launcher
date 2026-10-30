"""Dépendances Python : `requirements.txt` du noyau et de chaque extension, un seul venv.

Stdlib seulement : importé par bootstrap.pyw avant l'installation de PySide6.
Un extension dont l'installation échoue est mise de côté (core/data/deps_failed.json),
le lanceur démarre quand même.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from core.api import write_json_atomic
from core.paths import DATA_DIR, EXTENSIONS_DIR, PYTHON, ROOT, VENV, WHEELS_DIR

CORE_ID = "core"
HASH_FILE = VENV / ".deps_hash"
FAILED_FILE = DATA_DIR / "deps_failed.json"


def requirement_files() -> dict[str, Path]:
    """`id` → requirements.txt : le noyau d'abord, puis les extensions par ordre alphabétique."""
    files = {CORE_ID: ROOT / "requirements.txt"}
    if EXTENSIONS_DIR.is_dir():
        for folder in sorted(EXTENSIONS_DIR.iterdir()):
            path = folder / "requirements.txt"
            if path.is_file():
                files[folder.name] = path
    return files


def deps_hash() -> str:
    """Empreinte de tous les fichiers (identifiant + contenu) : pip ne repasse que si elle change."""
    digest = hashlib.sha256()
    for ext_id, path in requirement_files().items():
        digest.update(ext_id.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def deps_outdated() -> bool:
    try:
        return HASH_FILE.read_text(encoding="utf-8-sig") != deps_hash()
    except OSError:
        return True


def load_failed() -> set[str]:
    """Extensions dont les dépendances n'ont pas pu être installées."""
    try:
        data = json.loads(FAILED_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return set()
    return {i for i in data if isinstance(i, str)} if isinstance(data, list) else set()


def _pip_install(path: Path) -> bool:
    """Installe un requirements.txt ; avec un dossier `wheels/` (zip autonome), d'abord sans réseau."""
    command = [str(PYTHON), "-m", "pip", "install", "-r", str(path)]
    if WHEELS_DIR.is_dir():
        offline = subprocess.run(
            [*command, "--no-index", "--find-links", str(WHEELS_DIR)], creationflags=subprocess.CREATE_NO_WINDOW
        )
        if offline.returncode == 0:
            return True
    return subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW).returncode == 0


def install_deps(set_status=lambda text: None) -> list[str] | None:
    """Installe le noyau puis chaque extension, séparément.

    None si le noyau échoue (le lanceur ne peut pas démarrer) ; sinon la liste des
    extensions en échec (vide si tout va bien). Le hash n'est écrit qu'après le noyau.
    """
    files = requirement_files()
    set_status("Installation des dépendances du noyau…")
    if not _pip_install(files.pop(CORE_ID)):
        return None
    failed = []
    for ext_id, path in files.items():
        set_status(f"Dépendances : {ext_id}…")
        if not _pip_install(path):
            failed.append(ext_id)
    write_json_atomic(FAILED_FILE, failed)
    HASH_FILE.write_text(deps_hash(), encoding="utf-8")
    return failed
