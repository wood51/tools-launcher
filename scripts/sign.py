"""Clés et signature des extensions (ligne de commande ; l'extension « Publication » fait la même chose en fenêtre).

Usage : python scripts/sign.py keygen <id> "<Nom affiché>" [--ids a,b]
        python scripts/sign.py sign-zip <fichier.zip> [--key-id ID] [--out SORTIE.zip]
        python scripts/sign.py resign-catalog <DOSSIER_CATALOGUE> [--key-id ID]
        python scripts/sign.py fingerprint            (empreintes des clés de confiance)
        python scripts/sign.py verify <FICHIER>      (vérifie FICHIER.sig, ex. SHA256SUMS d'une release)

`keygen` crée une clé privée chiffrée par mot de passe dans ~/.tools_launcher_signing/<id>.key (HORS du dépôt) et
ajoute la clé publique à core/assets/trusted_keys.json (à commiter : le lanceur ne fait confiance qu'à ces clés ;
`--ids` limite la clé à certaines extensions). Sauvegarder la clé privée hors ligne.
`sign-zip` ajoute SIGNATURE.json à un zip. `resign-catalog` signe tous les zips d'un catalogue existant et met à
jour leur empreinte dans index.json : réservé à un catalogue de confiance, signer c'est se porter garant du contenu.
"""

import argparse
import getpass
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.api import write_json_atomic  # noqa: E402
from core.installer import InstallError, sha256_file  # noqa: E402
from core.publishing import sign_zip  # noqa: E402
from core.signing import TRUSTED_FILE, add_trusted_key, generate_key, key_path, fingerprint, trusted_keys, verify_raw  # noqa: E402


def pick_key(key_id: str | None) -> tuple[str, Path] | None:
    keys = trusted_keys()
    key_id = key_id or (next(iter(keys)) if len(keys) == 1 else None)
    if key_id not in keys:
        print("Clé inconnue ou ambiguë : donner --key-id (voir core/assets/trusted_keys.json).")
        return None
    path = key_path(key_id)
    if not path.is_file():
        print(f"Clé privée introuvable : {path}")
        return None
    return key_id, path


def keygen(args: argparse.Namespace) -> int:
    if args.id in trusted_keys():
        print(f"La clé « {args.id} » existe déjà dans {TRUSTED_FILE.name}.")
        return 1
    passphrase = getpass.getpass("Mot de passe de la clé privée : ")
    if len(passphrase) < 12 or passphrase != getpass.getpass("Confirmer : "):
        print("Mot de passe trop court (12 caractères minimum) ou différent.")
        return 1
    path = key_path(args.id)
    try:
        public = generate_key(path, passphrase.encode("utf-8"))
    except FileExistsError as e:
        print(e)
        return 1
    ids = [i for i in (args.ids or "").split(",") if i]
    add_trusted_key(args.id, args.name, public, ids or None)
    print(f"Clé privée : {path}\nClé publique ajoutée à {TRUSTED_FILE} : à commiter.")
    print("Sauvegardez la clé privée hors ligne (clé USB rangée) ; ne la mettez jamais dans un dépôt.")
    return 0


def sign_one(args: argparse.Namespace) -> int:
    picked = pick_key(args.key_id)
    if picked is None:
        return 1
    key_id, path = picked
    out = args.out or args.zip.with_name(args.zip.stem + "-signed.zip")
    passphrase = getpass.getpass("Mot de passe de la clé de signature : ").encode("utf-8")
    try:
        report = sign_zip(args.zip, out, path, key_id, passphrase)
    except (InstallError, ValueError, OSError) as e:
        print(f"Signature impossible : {e}")
        return 1
    print(f"{report.id} {report.version} signé par {report.signer} -> {out}")
    return 0


def resign_catalog(args: argparse.Namespace) -> int:
    picked = pick_key(args.key_id)
    if picked is None:
        return 1
    key_id, path = picked
    index_path = args.catalog / "index.json"
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8-sig"))["extensions"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"index.json illisible : {e}")
        return 1
    print(f"Catalogue : {args.catalog}")
    for entry in entries:
        try:
            ok = sha256_file(args.catalog / entry["zip"]) == entry["sha256"].lower()
        except (OSError, KeyError, AttributeError):
            ok = False
        print(f"  {'OK    ' if ok else 'ERREUR'} {entry.get('id')} {entry.get('version')}")
        if not ok:
            print("Un zip est absent ou ne correspond pas à son empreinte : rien n'est signé.")
            return 1
    if input("Signer ce contenu ? (o/N) ").strip().lower() != "o":
        return 1
    passphrase = getpass.getpass("Mot de passe de la clé de signature : ").encode("utf-8")
    with tempfile.TemporaryDirectory() as work:
        signed = []
        for entry in entries:
            target = Path(work) / Path(entry["zip"]).name
            try:
                report = sign_zip(args.catalog / entry["zip"], target, path, key_id, passphrase)
            except (InstallError, ValueError, OSError) as e:
                print(f"{entry.get('id')} : {e}\nRien n'est modifié.")
                return 1
            signed.append((entry, target, report))
        for entry, target, report in signed:
            (args.catalog / entry["zip"]).write_bytes(target.read_bytes())
            entry["sha256"] = sha256_file(args.catalog / entry["zip"])
            entry["author"] = report.author
        write_json_atomic(index_path, {"extensions": entries})
    print(f"{len(entries)} zip(s) signé(s) par {key_id}.")
    return 0


def verify_file(args: argparse.Namespace) -> int:
    signature = args.file.with_name(args.file.name + ".sig")
    try:
        signer = verify_raw(args.file.read_bytes(), signature.read_bytes())
    except (OSError, ValueError) as e:
        print(f"Vérification impossible : {e}")
        return 1
    print(f"Signature valide : {signer}")
    return 0


def show_fingerprints(args: argparse.Namespace) -> int:
    for key in trusted_keys().values():
        scope = f" (limitée à : {', '.join(key['ids'])})" if isinstance(key.get("ids"), list) else ""
        print(f"{key['id']} · {key.get('name', '')}{scope}")
        print(f"  {fingerprint(key['public'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("keygen")
    p.add_argument("id")
    p.add_argument("name")
    p.add_argument("--ids", help="extensions que cette clé peut signer, séparées par des virgules")
    p.set_defaults(run=keygen)
    p = sub.add_parser("sign-zip")
    p.add_argument("zip", type=Path)
    p.add_argument("--key-id")
    p.add_argument("--out", type=Path)
    p.set_defaults(run=sign_one)
    p = sub.add_parser("resign-catalog")
    p.add_argument("catalog", type=Path)
    p.add_argument("--key-id")
    p.set_defaults(run=resign_catalog)
    p = sub.add_parser("fingerprint")
    p.set_defaults(run=show_fingerprints)
    p = sub.add_parser("verify")
    p.add_argument("file", type=Path)
    p.set_defaults(run=verify_file)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
