from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import base64, os, re

WRAP_PREFIX = "x1."
WRAP_INFO = b"webfluid-mobile-x1"
KEY_LENGTH = 32
NONCE_LENGTH = 12
SIGNATURE_LENGTH = 64

_BASE64URL = re.compile(r"^[A-Za-z0-9_-]*$")


def b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64decode(text: str) -> bytes:
    if not isinstance(text, str) or not _BASE64URL.match(text) or len(text) % 4 == 1:
        raise ValueError("INVALID_ENCODING")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _raw(key: X25519PublicKey) -> bytes:
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def enc_key(text: str) -> X25519PublicKey:
    raw = b64decode(text)
    if len(raw) != KEY_LENGTH: raise ValueError("INVALID_KEY")
    key = X25519PublicKey.from_public_bytes(raw)
    X25519PrivateKey.generate().exchange(key)
    return key


def sig_key(text: str) -> Ed25519PublicKey:
    raw = b64decode(text)
    if len(raw) != KEY_LENGTH: raise ValueError("INVALID_KEY")
    return Ed25519PublicKey.from_public_bytes(raw)


def valid_keys(enc_pubkey: str, sig_pubkey: str) -> bool:
    try:
        enc_key(enc_pubkey)
        sig_key(sig_pubkey)
        return True
    except ValueError: return False


def wrap(enc_pubkey: str, data: bytes) -> str:
    recipient = enc_key(enc_pubkey)
    ephemeral = X25519PrivateKey.generate()
    epk = _raw(ephemeral.public_key())

    key = HKDF(
        algorithm=hashes.SHA256(), length=KEY_LENGTH,
        salt=epk + _raw(recipient), info=WRAP_INFO
    ).derive(ephemeral.exchange(recipient))

    nonce = os.urandom(NONCE_LENGTH)
    sealed = AESGCM(key).encrypt(nonce, data, None)
    return WRAP_PREFIX + b64encode(epk + nonce + sealed)


def verify(sig_pubkey: str, message: str, signature: str) -> bool:
    try:
        raw = b64decode(signature)
        if len(raw) != SIGNATURE_LENGTH: return False
        sig_key(sig_pubkey).verify(raw, message.encode("utf-8"))
        return True
    except (ValueError, TypeError, InvalidSignature): return False
