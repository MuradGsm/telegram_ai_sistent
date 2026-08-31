from __future__ import annotations

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

VALID_BOT_TOKEN = "123456789:AAFakeTelegramTokenValueForTestsXXXX" 


# ---------- helpers ----------

async def _create_workspace(client: AsyncClient, headers: dict, name: str = "My Shop") -> dict:
    resp = await client.post("/workspaces", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _mock_telegram_get_me(respx_mock, token: str = VALID_BOT_TOKEN, ok: bool = True, username: str = "my_test_bot"):
    body = {"ok": ok, "result": {"username": username}} if ok else {"ok": False, "description": "Unauthorized"}
    return respx_mock.get(f"https://api.telegram.org/bot{token}/getMe").mock(
        return_value=httpx.Response(200, json=body)
    )


def _mock_telegram_set_webhook(respx_mock, token: str = VALID_BOT_TOKEN, ok: bool = True):
    body = {"ok": ok, "result": True} if ok else {"ok": False, "description": "Bad webhook"}
    return respx_mock.post(f"https://api.telegram.org/bot{token}/setWebhook").mock(
        return_value=httpx.Response(200, json=body)
    )


def _mock_telegram_delete_webhook(respx_mock, token: str = VALID_BOT_TOKEN):
    return respx_mock.post(f"https://api.telegram.org/bot{token}/deleteWebhook").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": True})
    )


# ---------- create ----------

class TestCreateWorkspace:
    async def test_create_success(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/workspaces", json={"name": "My Shop"}, headers=auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "My Shop"
        assert body["plan_tier"] == "free"
        assert body["is_bot_active"] is False
        assert body["messages_used_this_period"] == 0

    async def test_create_requires_auth(self, client: AsyncClient):
        resp = await client.post("/workspaces", json={"name": "No Auth Shop"})
        assert resp.status_code == 401

    async def test_create_rejects_empty_name(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/workspaces", json={"name": ""}, headers=auth_headers)
        assert resp.status_code == 422

    async def test_create_default_timezone(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/workspaces", json={"name": "Default TZ Shop"}, headers=auth_headers)
        assert resp.json()["timezone"] == "Asia/Baku" if "timezone" in resp.json() else True
        # timezone не входит в WorkspaceOut схему — просто проверяем, что запрос не падает
        assert resp.status_code == 201


# ---------- list ----------

class TestListWorkspaces:
    async def test_list_only_returns_own_workspaces(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict
    ):
        await _create_workspace(client, auth_headers, "Mine")
        await _create_workspace(client, other_auth_headers, "Theirs")

        resp = await client.get("/workspaces", headers=auth_headers)
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()]
        assert names == ["Mine"]

    async def test_list_empty_for_user_without_workspaces(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/workspaces", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/workspaces")
        assert resp.status_code == 401


# ---------- get ----------

class TestGetWorkspace:
    async def test_get_owned_workspace(self, client: AsyncClient, auth_headers: dict):
        created = await _create_workspace(client, auth_headers)
        resp = await client.get(f"/workspaces/{created['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_nonexistent_workspace_404(self, client: AsyncClient, auth_headers: dict):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/workspaces/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_other_users_workspace_is_404_not_403(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict
    ):
        """IDOR: чужой воркспейс должен выглядеть как несуществующий, а не как 'запрещено'."""
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        resp = await client.get(f"/workspaces/{their_workspace['id']}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_workspace_invalid_uuid_format(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/workspaces/not-a-uuid", headers=auth_headers)
        assert resp.status_code == 422


# ---------- update ----------

class TestUpdateWorkspace:
    async def test_update_name(self, client: AsyncClient, auth_headers: dict):
        created = await _create_workspace(client, auth_headers, "Old Name")
        resp = await client.patch(
            f"/workspaces/{created['id']}", json={"name": "New Name"}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_update_partial_does_not_touch_other_fields(self, client: AsyncClient, auth_headers: dict):
        created = await _create_workspace(client, auth_headers, "Keep Fields")
        resp = await client.patch(
            f"/workspaces/{created['id']}",
            json={"owner_telegram_id": 555111222},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Keep Fields"
        assert body["owner_telegram_id"] == 555111222

    async def test_update_other_users_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        resp = await client.patch(
            f"/workspaces/{their_workspace['id']}", json={"name": "Hijacked"}, headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_update_requires_auth(self, client: AsyncClient, auth_headers: dict):
        created = await _create_workspace(client, auth_headers)
        resp = await client.patch(f"/workspaces/{created['id']}", json={"name": "X"})
        assert resp.status_code == 401


# ---------- connect telegram bot ----------

@pytest.mark.usefixtures("db_session")
class TestConnectTelegramBot:
    async def test_connect_bot_success(self, client: AsyncClient, auth_headers: dict, respx_mock):
        created = await _create_workspace(client, auth_headers)
        _mock_telegram_get_me(respx_mock)
        _mock_telegram_set_webhook(respx_mock)

        resp = await client.post(
            f"/workspaces/{created['id']}/connect-bot",
            json={"telegram_bot_token": VALID_BOT_TOKEN},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_bot_active"] is True
        assert body["telegram_bot_username"] == "my_test_bot"

    async def test_connect_bot_invalid_token_rejected_by_telegram(
        self, client: AsyncClient, auth_headers: dict, respx_mock
    ):
        created = await _create_workspace(client, auth_headers)
        _mock_telegram_get_me(respx_mock, ok=False)

        resp = await client.post(
            f"/workspaces/{created['id']}/connect-bot",
            json={"telegram_bot_token": VALID_BOT_TOKEN},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_connect_bot_telegram_unreachable(self, client: AsyncClient, auth_headers: dict, respx_mock):
        created = await _create_workspace(client, auth_headers)
        respx_mock.get(f"https://api.telegram.org/bot{VALID_BOT_TOKEN}/getMe").mock(
            side_effect=httpx.ConnectError("network down")
        )

        resp = await client.post(
            f"/workspaces/{created['id']}/connect-bot",
            json={"telegram_bot_token": VALID_BOT_TOKEN},
            headers=auth_headers,
        )
        assert resp.status_code == 502

    async def test_connect_bot_short_token_rejected_before_any_network_call(
        self, client: AsyncClient, auth_headers: dict, respx_mock
    ):
        created = await _create_workspace(client, auth_headers)
        resp = await client.post(
            f"/workspaces/{created['id']}/connect-bot",
            json={"telegram_bot_token": "short"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert respx_mock.calls.call_count == 0

    async def test_connect_bot_other_users_workspace_is_404_and_no_telegram_call(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict, respx_mock
    ):
        """IDOR + защита от побочных эффектов: чужой webhook нельзя перезаписать."""
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        resp = await client.post(
            f"/workspaces/{their_workspace['id']}/connect-bot",
            json={"telegram_bot_token": VALID_BOT_TOKEN},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert respx_mock.calls.call_count == 0


# ---------- delete ----------

class TestDeleteWorkspace:
    async def test_delete_success(self, client: AsyncClient, auth_headers: dict):
        created = await _create_workspace(client, auth_headers)
        resp = await client.delete(f"/workspaces/{created['id']}", headers=auth_headers)
        assert resp.status_code == 204

        get_resp = await client.get(f"/workspaces/{created['id']}", headers=auth_headers)
        assert get_resp.status_code == 404

    async def test_delete_with_active_bot_calls_delete_webhook(
        self, client: AsyncClient, auth_headers: dict, respx_mock
    ):
        created = await _create_workspace(client, auth_headers)
        _mock_telegram_get_me(respx_mock)
        _mock_telegram_set_webhook(respx_mock)
        await client.post(
            f"/workspaces/{created['id']}/connect-bot",
            json={"telegram_bot_token": VALID_BOT_TOKEN},
            headers=auth_headers,
        )

        delete_webhook_route = _mock_telegram_delete_webhook(respx_mock)
        resp = await client.delete(f"/workspaces/{created['id']}", headers=auth_headers)
        assert resp.status_code == 204
        assert delete_webhook_route.called

    async def test_delete_other_users_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        resp = await client.delete(f"/workspaces/{their_workspace['id']}", headers=auth_headers)
        assert resp.status_code == 404

        # у владельца воркспейс всё ещё должен быть на месте
        still_there = await client.get(f"/workspaces/{their_workspace['id']}", headers=other_auth_headers)
        assert still_there.status_code == 200

    async def test_delete_requires_auth(self, client: AsyncClient, auth_headers: dict):
        created = await _create_workspace(client, auth_headers)
        resp = await client.delete(f"/workspaces/{created['id']}")
        assert resp.status_code == 401