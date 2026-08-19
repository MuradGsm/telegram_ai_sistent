import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher


from app.core.conf import settings

password_hash = PasswordHash((BcryptHasher(),))


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(password_hash.hash, password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await asyncio.to_thread(password_hash.verify, plain_password, hashed_password)


def _create_token(
    subject: UUID,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: UUID) -> str:
    return _create_token(
        user_id,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Could not validate token") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Expected token type '{expected_type}'")

    if not payload.get("sub"):
        raise InvalidTokenError("Token is missing subject")

    return payload