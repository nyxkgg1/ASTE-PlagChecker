from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from app.core.config import settings


# Argon2id is the recommended password-hashing algorithm here.
password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,   # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    The returned value contains the algorithm parameters
    and salt, so no separate salt column is required.
    """
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """
    Verify a plaintext password against an Argon2id hash.
    """
    try:
        return password_hasher.verify(
            password_hash,
            plain_password,
        )
    except (VerificationError, InvalidHashError):
        return False


def needs_password_rehash(password_hash: str) -> bool:
    """
    Check whether the stored hash uses outdated parameters.
    """
    return password_hasher.check_needs_rehash(password_hash)


def create_access_token(
    user_id: str,
    username: str,
    roles: list[str],
) -> str:

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )

        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        if not payload.get("sub"):
            raise ValueError("Invalid token subject")

        return payload

    except JWTError as exc:
        raise ValueError(
            "Invalid or expired access token"
        ) from exc