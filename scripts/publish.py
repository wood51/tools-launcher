"""Publie une extension dans un catalogue : zip signé versionné + entrée dans index.json.

Usage : python scripts/publish.py <id | fichier.zip> [--notes "texte"] [--catalog DOSSIER] [--key-id ID] [--force]
Un identifiant d'extension est empaqueté depuis extensions/<id> ; un zip est signé tel quel.
Sans --catalog, le premier dossier actif des sources du Catalogue est utilisé (pour un dépôt Git : un clone local,
à commiter puis pousser ensuite). Une version déjà publiée ne s'écrase pas (sauf --force).
"""

import argparse
import getpass
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.catalog.index import load_source  # noqa: E402
from core.installer import InstallError  # noqa: E402
from core.paths import EXTENSIONS_DIR  # noqa: E402
from core.publishing import publish_zip, sign_zip, zip_from_folder  # noqa: E402
from core.signing import key_path, trusted_keys  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", help="identifiant d'extension ou fichier .zip")
    parser.add_argument("--notes", default="")
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--key-id", help="clé de signature (défaut : la seule clé de confiance)")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    keys = trusted_keys()
    key_id = args.key_id or (next(iter(keys)) if len(keys) == 1 else None)
    if key_id not in keys or not key_path(key_id).is_file():
        print("Clé de signature inconnue, ambiguë ou introuvable : créez-la avec scripts/sign.py keygen, ou donnez --key-id.")
        return 1
    catalog = args.catalog or load_source()
    if catalog is None:
        print("Aucun catalogue : donner --catalog ou ajouter un dossier dans Catalogue > Source…")
        return 1

    passphrase = getpass.getpass("Mot de passe de la clé de signature : ").encode("utf-8")
    with tempfile.TemporaryDirectory() as work:
        source = Path(args.target)
        try:
            if source.suffix.lower() != ".zip":
                source = zip_from_folder(EXTENSIONS_DIR / args.target, Path(work) / "pack.zip")
            report = sign_zip(source, Path(work) / "signed.zip", key_path(key_id), key_id, passphrase)
            entry = publish_zip(catalog, Path(work) / "signed.zip", args.notes, args.force)
        except (InstallError, ValueError, OSError) as e:
            print(f"Publication impossible : {e}")
            return 1
    print(f"Publié : {entry['id']} {entry['version']} (signé par {report.signer}) -> {catalog / entry['zip']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
