"""Password hashing (Argon2id), JWT access tokens and opaque refresh tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.errors import Unauthorized

_hasher = PasswordHasher()  # Argon2id, library defaults (RFC 9106 low-memory profile)

# Used to keep login timing similar whether or not the account exists.
_DUMMY_HASH = _hasher.hash("qatra-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        ok = _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return ok and password_hash is not None


def create_access_token(user_id: uuid.UUID, roles: list[str]) -> tuple[str, datetime]:
    s = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=s.access_token_minutes)
    claims = {
        "sub": str(user_id),
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": exp,
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(claims, s.jwt_secret.get_secret_value(), algorithm=s.jwt_algorithm)
    return token, exp


def decode_access_token(token: str) -> uuid.UUID:
    s = get_settings()
    try:
        claims = jwt.decode(
            token,
            s.jwt_secret.get_secret_value(),
            algorithms=[s.jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Access token expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid access token") from exc
    if claims.get("type") != "access":
        raise Unauthorized("Invalid token type")
    try:
        return uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise Unauthorized("Invalid token subject") from exc


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
