"""Signature des extensions (Ed25519) : clés fournies avec le launcher et clés publiques approuvées localement.

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
from core.paths import ASSETS_DIR, DATA_DIR

TRUSTED_FILE = ASSETS_DIR / "trusted_keys.json"
LOCAL_TRUSTED_FILE = DATA_DIR / "trusted_keys.json"
SIGNATURE_NAME = "SIGNATURE.json"
KEY_DIR = Path.home() / ".tools_launcher_signing"


def _read_trust_file(path: Path, strict: bool = False) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {"keys": [], "disabled": []}
    except (OSError, ValueError):
        if strict:
            raise ValueError("La liste locale des clés est illisible ; elle a été conservée.") from None
        return {"keys": [], "disabled": []}
    keys = data.get("keys") if isinstance(data, dict) else None
    disabled = data.get("disabled", []) if isinstance(data, dict) else []
    if not isinstance(keys, list) or any(not isinstance(key, dict) or not isinstance(key.get("id"), str)
                                         or not isinstance(key.get("public"), str) for key in keys) \
            or not isinstance(disabled, list) or any(not isinstance(key_id, str) for key_id in disabled):
        if strict:
            raise ValueError("Le format de la liste des clés est invalide ; elle a été conservée.")
        return {"keys": [], "disabled": []}
    return {"keys": keys, "disabled": disabled}


def _read_keys(path: Path, strict: bool = False) -> dict[str, dict]:
    return {key["id"]: key for key in _read_trust_file(path, strict)["keys"]}


def trusted_keys() -> dict[str, dict]:
    """Clés par id. Les clés fournies avec le launcher priment, notamment leurs révocations."""
    try:
        local = _read_trust_file(LOCAL_TRUSTED_FILE, strict=True)
    except ValueError:
        return {}  # Une liste locale corrompue ne doit pas réactiver des clés désapprouvées.
    keys = {**{key["id"]: key for key in local["keys"]}, **_read_keys(TRUSTED_FILE)}
    for key_id in local["disabled"]:
        if key_id in keys and keys[key_id].get("revoked") is not True:
            keys[key_id] = {**keys[key_id], "revoked": True, "disabled_locally": True}
    return keys


def set_key_trust(key_id: str, trusted: bool) -> None:
    """Retire ou rétablit la confiance locale ; une révocation distribuée reste définitive."""
    local = _read_trust_file(LOCAL_TRUSTED_FILE, strict=True)
    keys = {**{key["id"]: key for key in local["keys"]}, **_read_keys(TRUSTED_FILE)}
    key = keys.get(key_id)
    if key is None:
        raise ValueError("Clé publique introuvable.")
    if trusted and key.get("revoked") is True:
        raise ValueError("Une clé révoquée par son distributeur ne peut pas être réactivée.")
    disabled = set(local["disabled"])
    if trusted:
        disabled.discard(key_id)
    else:
        disabled.add(key_id)
    write_json_atomic(LOCAL_TRUSTED_FILE, {"keys": local["keys"], "disabled": sorted(disabled)})


def validate_public_key(data: object) -> dict:
    """Lit uniquement les champs publics du format .pub.json et valide Ed25519."""
    from core.registry import EXTENSION_ID

    if not isinstance(data, dict):
        raise ValueError("Un fichier de clé publique doit contenir un objet JSON.")
    key_id, name, public = data.get("id"), data.get("name"), data.get("public")
    if not isinstance(key_id, str) or not EXTENSION_ID.fullmatch(key_id):
        raise ValueError("Identifiant de clé invalide.")
    if not isinstance(name, str) or not name.strip() or not isinstance(public, str):
        raise ValueError("Le nom et la clé publique sont obligatoires.")
    try:
        raw = base64.b64decode(public, validate=True)
        if len(raw) != 32:
            raise ValueError()
    except (ValueError, binascii.Error):
        raise ValueError("Clé publique Ed25519 invalide : 32 octets en base64 attendus.") from None
    if data.get("revoked") is True:
        raise ValueError("Une clé révoquée ne peut pas être approuvée.")
    entry = {"id": key_id, "name": name.strip(), "public": base64.b64encode(raw).decode("ascii")}
    if "ids" in data:
        ids = data["ids"]
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not EXTENSION_ID.fullmatch(i) for i in ids):
            raise ValueError("La liste des outils autorisés est invalide.")
        entry["ids"] = list(dict.fromkeys(ids))
    return entry


def read_public_key(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(65_537)
    if len(raw) > 65_536:
        raise ValueError("Ce fichier est trop volumineux pour une clé publique.")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError):
        raise ValueError("Fichier de clé publique illisible. Choisissez un fichier .pub.json, sans clé privée.") from None
    return validate_public_key(data)


def import_public_key(data: dict) -> None:
    """Approuve localement une clé validée, sans changer les clés distribuées."""
    entry = validate_public_key(data)
    local = _read_trust_file(LOCAL_TRUSTED_FILE, strict=True)
    existing = trusted_keys().get(entry["id"])
    if existing is not None:
        if existing.get("disabled_locally"):
            raise ValueError("La confiance de cette clé a été retirée. Utilisez Rétablir la confiance dans la liste.")
        if existing.get("revoked") is True:
            raise ValueError("Cette clé a été révoquée et ne peut pas être réactivée par import.")
        if existing["public"] != entry["public"]:
            raise ValueError("Une autre clé utilise déjà cet identifiant. Elle ne sera pas remplacée.")
        raise ValueError("Cette clé est déjà approuvée. Ses autorisations actuelles sont conservées.")
    write_json_atomic(LOCAL_TRUSTED_FILE, {"keys": [*local["keys"], entry], "disabled": local["disabled"]})


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
    keys = _read_keys(TRUSTED_FILE, strict=True)
    if key_id in keys or key_id in trusted_keys():
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
    if key is None or key_id not in _read_keys(TRUSTED_FILE) or key.get("revoked") is True or "ids" in key:
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
