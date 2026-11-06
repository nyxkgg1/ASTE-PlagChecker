import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _get_key() -> bytes:
    key_string = settings.response_encryption_key.strip()

    # Restore missing Base64 padding if necessary
    padding = "=" * (-len(key_string) % 4)
    key_string += padding

    try:
        key = base64.urlsafe_b64decode(key_string)
    except Exception as exc:
        raise ValueError("Invalid RESPONSE_ENCRYPTION_KEY") from exc

    if len(key) != 32:
        raise ValueError(
            "RESPONSE_ENCRYPTION_KEY must decode to exactly 32 bytes"
        )

    return key


def encrypt_json(data: dict) -> str:
    key = _get_key()

    aes = AESGCM(key)

    # AES-GCM uses a 12-byte nonce
    nonce = os.urandom(12)

    plaintext = json.dumps(
        data,
        separators=(",", ":")
    ).encode("utf-8")

    ciphertext = aes.encrypt(
        nonce,
        plaintext,
        None
    )

    # nonce + ciphertext
    encrypted_data = nonce + ciphertext

    return base64.urlsafe_b64encode(
        encrypted_data
    ).decode("utf-8")


def decrypt_json(encrypted_data: str) -> dict:
    key = _get_key()

    raw = base64.urlsafe_b64decode(
        encrypted_data + "=" * (-len(encrypted_data) % 4)
    )

    nonce = raw[:12]
    ciphertext = raw[12:]

    aes = AESGCM(key)

    plaintext = aes.decrypt(
        nonce,
        ciphertext,
        None
    )

    return json.loads(
        plaintext.decode("utf-8")
    )