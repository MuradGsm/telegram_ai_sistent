from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conf import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User


# ---------- helpers ----------

def _expired_token(user_id, token_type: str = "refresh") -> str:
    """Токен с истёкшим exp — для проверки, что decode_token его отклоняет."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------- register ----------

class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "StrongPass123!", "full_name": "New User"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@example.com"
        assert body["is_active"] is True
        assert "hashed_password" not in body
        assert "password" not in body

    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        resp = await client.post(
            "/auth/register",
            json={"email": test_user.email, "password": "AnotherPass123!"},
        )
        assert resp.status_code == 409

    async def test_register_duplicate_email_different_case(self, client: AsyncClient, test_user: User):
        """Репозиторий лоуеркейсит email — регистр не должен обходить уникальность."""
        resp = await client.post(
            "/auth/register",
            json={"email": test_user.email.upper(), "password": "AnotherPass123!"},
        )
        assert resp.status_code == 409

    async def test_register_short_password_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"email": "short@example.com", "password": "short1"},
        )
        assert resp.status_code == 422

    async def test_register_invalid_email_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "StrongPass123!"},
        )
        assert resp.status_code == 422

    async def test_register_response_never_leaks_password_field_names(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"email": "leak-check@example.com", "password": "StrongPass123!"},
        )
        assert resp.status_code == 201
        assert set(resp.json().keys()) == {"id", "email", "full_name", "is_active", "created_at"}


# ---------- login ----------

class TestLogin:
    async def test_login_success(self, client: AsyncClient, test_user: User):
        resp = await client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "TestPass123!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["access_token"] != body["refresh_token"]

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        resp = await client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "WrongPassword1!"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "WhoKnows123!"},
        )
        assert resp.status_code == 401

    async def test_login_error_message_identical_for_missing_user_and_wrong_password(
        self, client: AsyncClient, test_user: User
    ):
        """Ответ не должен позволять энумерацию email по тексту ошибки."""
        resp_no_user = await client.post(
            "/auth/login", json={"email": "ghost2@example.com", "password": "WhoKnows123!"}
        )
        resp_wrong_pass = await client.post(
            "/auth/login", json={"email": test_user.email, "password": "WrongPassword1!"}
        )
        assert resp_no_user.status_code == resp_wrong_pass.status_code == 401
        assert resp_no_user.json()["detail"] == resp_wrong_pass.json()["detail"]

    async def test_login_disabled_user(self, client: AsyncClient, db_session: AsyncSession, test_user: User):
        email = test_user.email  # читаем до expire_all(), иначе ленивая подгрузка вне greenlet упадёт
        test_user.is_active = False
        db_session.add(test_user)
        await db_session.flush()
        db_session.expire_all()

        resp = await client.post(
            "/auth/login",
            json={"email": email, "password": "TestPass123!"},
        )
        assert resp.status_code == 403

    async def test_login_short_password_fails_validation_before_db_hit(self, client: AsyncClient):
        resp = await client.post(
            "/auth/login", json={"email": "x@example.com", "password": "short"}
        )
        assert resp.status_code == 422


# ---------- refresh ----------

class TestRefresh:
    async def test_refresh_success_issues_new_pair(self, client: AsyncClient, test_user: User):
        refresh_token = create_refresh_token(test_user.id)
        resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["refresh_token"]

    async def test_refresh_rejects_access_token(self, client: AsyncClient, test_user: User):
        """Access-токен не должен приниматься как refresh (проверка claim 'type')."""
        access_token = create_access_token(test_user.id)
        resp = await client.post("/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401

    async def test_refresh_rejects_garbage_token(self, client: AsyncClient):
        resp = await client.post("/auth/refresh", json={"refresh_token": "not.a.jwt"})
        assert resp.status_code == 401

    async def test_refresh_rejects_expired_token(self, client: AsyncClient, test_user: User):
        expired = _expired_token(test_user.id, "refresh")
        resp = await client.post("/auth/refresh", json={"refresh_token": expired})
        assert resp.status_code == 401

    async def test_refresh_rejects_token_signed_with_wrong_secret(self, client: AsyncClient, test_user: User):
        now = datetime.now(timezone.utc)
        forged = jwt.encode(
            {"sub": str(test_user.id), "type": "refresh", "iat": now, "exp": now + timedelta(days=1)},
            "wrong-secret-not-the-real-one",
            algorithm=settings.jwt_algorithm,
        )
        resp = await client.post("/auth/refresh", json={"refresh_token": forged})
        assert resp.status_code == 401

    async def test_refresh_rejects_deleted_user(self, client: AsyncClient, db_session: AsyncSession, test_user: User):
        refresh_token = create_refresh_token(test_user.id)
        await db_session.delete(test_user)
        await db_session.flush()
        db_session.expire_all()

        resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401


# ---------- me ----------

class TestMe:
    async def test_me_requires_auth_header(self, client: AsyncClient):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_me_returns_current_user(self, client: AsyncClient, test_user: User, auth_headers: dict):
        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == test_user.email

    async def test_me_rejects_invalid_token(self, client: AsyncClient):
        resp = await client.get("/auth/me", headers={"Authorization": "Bearer garbage.token.value"})
        assert resp.status_code == 401

    async def test_me_rejects_refresh_token_used_as_access(self, client: AsyncClient, test_user: User):
        """Refresh-токен не должен давать доступ к защищённым эндпоинтам."""
        refresh_token = create_refresh_token(test_user.id)
        resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
        assert resp.status_code == 401

    async def test_me_rejects_malformed_auth_header(self, client: AsyncClient, auth_headers: dict):
        token = auth_headers["Authorization"].split(" ")[1]
        resp = await client.get("/auth/me", headers={"Authorization": token})  # без "Bearer "
        assert resp.status_code == 401

    async def test_me_rejects_token_for_deleted_user(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User, auth_headers: dict
    ):
        await db_session.delete(test_user)
        await db_session.flush()
        db_session.expire_all()

        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 401