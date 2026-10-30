"""Signature des extensions (Ed25519) : le lanceur ne fait confiance qu'aux clés de `core/assets/trusted_keys.json`.

Chaque zip d'extension embarque un fichier `SIGNATURE.json` (à côté de `extension.json`). La signature couvre
l'identifiant, la version et l'empreinte de tous les autres fichiers du paquet : modifier un octet, ou rejouer
une signature sur une autre extension ou version, la rend invalide. Une clé peut être limitée à certaines
extensions (`ids`) ; une clé `revoked` est refusée. La clé privée ne quitte jamais le poste de l'auteur.
`cryptography` n'est importé qu'à l'usage (le bootstrap n'en dépend pas).
"""

import base64
import binascii
import datetime
import hashlib
import json
from pathlib import Path

from core.api import write_json_atomic
from core.paths import ASSETS_DIR

TRUSTED_FILE = ASSETS_DIR / "trusted_keys.json"
SIGNATURE_NAME = "SIGNATURE.json"
KEY_DIR = Path.home() / ".tools_launcher_signing"


def trusted_keys() -> dict[str, dict]:
    """Clés de confiance par id : `{"id", "name", "public" (32 octets en base64), "ids"?, "revoked"?}`."""
    try:
        data = json.loads(TRUSTED_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    keys = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(keys, list):
        return {}
    return {k["id"]: k for k in keys if isinstance(k, dict) and isinstance(k.get("id"), str) and isinstance(k.get("public"), str)}


def package_message(extension_id: str, version: str, digest: str) -> bytes:
    return f"TLPKG1\n{extension_id}\n{version}\n{digest}".encode("utf-8")


def verify_package(extension_id: str, version: str, digest: str, signature_file: bytes) -> str:
    """Nom du signataire si la signature est valide, de confiance et autorisée pour cette extension.
    Lève ValueError (message pour l'utilisateur) sinon."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        data = json.loads(signature_file.decode("utf-8-sig"))
        key_id = data["key"]
        signature = base64.b64decode(data["signature"], validate=True)
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise ValueError(f"{SIGNATURE_NAME} illisible") from None
    key = trusted_keys().get(key_id) if isinstance(key_id, str) else None
    if key is None:
        raise ValueError(f"clé de signature inconnue : {key_id}")
    if key.get("revoked") is True:
        raise ValueError(f"clé de signature révoquée : {key_id}")
    allowed = key.get("ids")
    if isinstance(allowed, list) and extension_id not in allowed:
        raise ValueError(f"la clé « {key_id} » n'est pas autorisée à signer « {extension_id} »")
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public"], validate=True))
        public.verify(signature, package_message(extension_id, version, digest))
    except (InvalidSignature, ValueError, binascii.Error):
        raise ValueError("signature invalide : le paquet a été modifié ou n'est pas de son auteur") from None
    return str(key.get("name") or key_id)


#### Côté auteur ####


def list_private_keys() -> list[str]:
    """Ids des clés privées présentes dans `~/.tools_launcher_signing/`."""
    return sorted(p.stem for p in KEY_DIR.glob("*.key")) if KEY_DIR.is_dir() else []


def key_path(key_id: str) -> Path:
    return KEY_DIR / f"{key_id}.key"


def generate_key(path: Path, passphrase: bytes) -> str:
    """Crée une clé privée chiffrée par mot de passe dans `path` ; renvoie la clé publique (base64)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if path.exists():
        raise FileExistsError(f"{path} existe déjà : rien n'est écrasé")
    private = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(passphrase),
        )
    )
    return public_key_of(path, passphrase)


def _load_private(path: Path, passphrase: bytes):
    from cryptography.hazmat.primitives import serialization

    try:
        return serialization.load_pem_private_key(path.read_bytes(), password=passphrase)
    except (ValueError, TypeError):
        raise ValueError("mot de passe incorrect ou clé illisible") from None


def public_key_of(path: Path, passphrase: bytes) -> str:
    """Clé publique (base64) d'une clé privée ; lève ValueError si le mot de passe est faux."""
    from cryptography.hazmat.primitives import serialization

    private = _load_private(path, passphrase)
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(public).decode("ascii")


def sign_package(extension_id: str, version: str, digest: str, path: Path, key_id: str, passphrase: bytes) -> bytes:
    """Contenu de `SIGNATURE.json`. Lève ValueError si le mot de passe est faux."""
    from cryptography.hazmat.primitives import serialization

    private = _load_private(path, passphrase)
    signature = private.sign(package_message(extension_id, version, digest))
    document = {
        "key": key_id,
        "id": extension_id,
        "version": version,
        "signed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def add_trusted_key(key_id: str, name: str, public: str, ids: list[str] | None = None) -> None:
    """Ajoute une clé publique à `trusted_keys.json` (à commiter : le lanceur ne fait confiance qu'à ces clés)."""
    keys = trusted_keys()
    if key_id in keys:
        raise ValueError(f"la clé « {key_id} » existe déjà")
    entry = {"id": key_id, "name": name, "public": public}
    if ids:
        entry["ids"] = ids
    write_json_atomic(TRUSTED_FILE, {"keys": [*keys.values(), entry]})


#### Fichiers quelconques (SHA256SUMS d'une release) ####


def sign_raw(raw: bytes, path: Path, key_id: str, passphrase: bytes) -> bytes:
    """Signature détachée d'un fichier (message distinct de celui des paquets : pas de confusion possible)."""
    private = _load_private(path, passphrase)
    signature = private.sign(b"TLRAW1\n" + raw)
    document = {
        "key": key_id,
        "signed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def verify_raw(raw: bytes, signature_file: bytes) -> str:
    """Nom du signataire d'un fichier signé par `sign_raw` ; lève ValueError. Les clés limitées à des
    extensions (`ids`) ne peuvent pas signer de release."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        data = json.loads(signature_file.decode("utf-8-sig"))
        key_id = data["key"]
        signature = base64.b64decode(data["signature"], validate=True)
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise ValueError("fichier de signature illisible") from None
    key = trusted_keys().get(key_id) if isinstance(key_id, str) else None
    if key is None or key.get("revoked") is True or "ids" in key:
        raise ValueError(f"clé non autorisée à signer une release : {key_id}")
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public"], validate=True))
        public.verify(signature, b"TLRAW1\n" + raw)
    except (InvalidSignature, ValueError, binascii.Error):
        raise ValueError("signature invalide") from None
    return str(key.get("name") or key_id)


def fingerprint(public: str) -> str:
    """Empreinte lisible d'une clé publique (SHA-256 de ses 32 octets, groupes de 4), à comparer par un autre canal."""
    digest = hashlib.sha256(base64.b64decode(public)).hexdigest()
    return " ".join(digest[i : i + 4] for i in range(0, 64, 4))
