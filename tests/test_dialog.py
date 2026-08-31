from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from httpx import AsyncClient

from app.core.enums import DialogStatus, MessageSender
from app.models.dialog import Dialog
from app.models.workspace import Workspace
from app.repositories.dialog_repository import DialogRepository


# ---------- fixtures ----------

@pytest.fixture
def mock_bot(monkeypatch):
    """Успешная отправка — просто копит отправленные сообщения."""
    import app.api.v1.dialogs as dialogs_module

    sent: list[dict] = []

    class _FakeBot:
        def __init__(self, token=None):
            self.token = token

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def send_message(self, chat_id, text):
            sent.append({"token": self.token, "chat_id": chat_id, "text": text})

    monkeypatch.setattr(dialogs_module, "Bot", _FakeBot)
    return sent


@pytest.fixture
def mock_bot_failing(monkeypatch):
    """Telegram отвечает ошибкой на send_message — для проверки 502-сценария."""
    import app.api.v1.dialogs as dialogs_module
    from aiogram.exceptions import TelegramAPIError

    class _FakeBot:
        def __init__(self, token=None):
            self.token = token

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def send_message(self, chat_id, text):
            raise TelegramAPIError(method=None, message="Bot was blocked by the user")

    monkeypatch.setattr(dialogs_module, "Bot", _FakeBot)


# ---------- helpers ----------

async def _create_workspace(client: AsyncClient, headers: dict, name: str = "Dialog Shop") -> dict:
    resp = await client.post("/workspaces", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _set_bot_token(db_session: AsyncSession, workspace_id: str, token: str = "123456:FAKEBOTTOKEN") -> None:
    result = await db_session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one()
    workspace.telegram_bot_token = token
    workspace.is_bot_active = True
    await db_session.flush()
    db_session.expire_all()


async def _create_dialog(
    db_session: AsyncSession,
    workspace_id: str,
    customer_telegram_id: int = 111222333,
    customer_display_name: str = "Test Customer",
) -> Dialog:
    repo = DialogRepository(db_session)
    return await repo.get_or_create(workspace_id, customer_telegram_id, customer_display_name)


# ---------- list ----------

class TestListDialogs:
    async def test_list_dialogs_for_workspace(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict
    ):
        workspace = await _create_workspace(client, auth_headers)
        await _create_dialog(db_session, workspace["id"], customer_telegram_id=1)
        await _create_dialog(db_session, workspace["id"], customer_telegram_id=2)

        resp = await client.get(f"/workspaces/{workspace['id']}/dialogs", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_list_filters_by_status(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict
    ):
        workspace = await _create_workspace(client, auth_headers)
        repo = DialogRepository(db_session)
        open_dialog = await _create_dialog(db_session, workspace["id"], customer_telegram_id=1)
        escalated_dialog = await _create_dialog(db_session, workspace["id"], customer_telegram_id=2)
        await repo.set_status(escalated_dialog, DialogStatus.ESCALATED)

        resp = await client.get(
            f"/workspaces/{workspace['id']}/dialogs",
            params={"status": "escalated"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == str(escalated_dialog.id)

    async def test_list_empty_workspace(self, client: AsyncClient, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        resp = await client.get(f"/workspaces/{workspace['id']}/dialogs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_other_users_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        resp = await client.get(f"/workspaces/{their_workspace['id']}/dialogs", headers=auth_headers)
        assert resp.status_code == 404

    async def test_list_requires_auth(self, client: AsyncClient, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        resp = await client.get(f"/workspaces/{workspace['id']}/dialogs")
        assert resp.status_code == 401

    async def test_list_rejects_invalid_limit(self, client: AsyncClient, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        resp = await client.get(
            f"/workspaces/{workspace['id']}/dialogs",
            params={"limit": 1000},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ---------- get ----------

class TestGetDialog:
    async def test_get_dialog_with_messages(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict
    ):
        workspace = await _create_workspace(client, auth_headers)
        dialog = await _create_dialog(db_session, workspace["id"])
        repo = DialogRepository(db_session)
        await repo.add_message(dialog, MessageSender.CUSTOMER, "What are your working hours?")
        await repo.add_message(dialog, MessageSender.BOT, "We are open 9 to 6.", tokens_used=42, confidence_score=0.8)

        resp = await client.get(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["messages"]) == 2
        assert body["messages"][0]["sender"] == "customer"
        assert body["messages"][1]["sender"] == "bot"
        assert body["messages"][1]["confidence_score"] == 0.8

    async def test_get_nonexistent_dialog_is_404(self, client: AsyncClient, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/workspaces/{workspace['id']}/dialogs/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_dialog_from_other_workspace_is_404(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict
    ):
        """IDOR внутри одного владельца: диалог из workspace A не виден через workspace B."""
        workspace_a = await _create_workspace(client, auth_headers, "A")
        workspace_b = await _create_workspace(client, auth_headers, "B")
        dialog = await _create_dialog(db_session, workspace_a["id"])

        resp = await client.get(
            f"/workspaces/{workspace_b['id']}/dialogs/{dialog.id}", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_get_dialog_in_other_users_workspace_is_404(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, other_auth_headers: dict
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        dialog = await _create_dialog(db_session, their_workspace["id"])

        resp = await client.get(
            f"/workspaces/{their_workspace['id']}/dialogs/{dialog.id}", headers=auth_headers
        )
        assert resp.status_code == 404


# ---------- reply ----------

class TestReplyToDialog:
    async def test_reply_success_sends_via_telegram_and_saves_message(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, mock_bot
    ):
        workspace = await _create_workspace(client, auth_headers)
        await _set_bot_token(db_session, workspace["id"])
        dialog = await _create_dialog(db_session, workspace["id"], customer_telegram_id=999)

        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/reply",
            json={"content": "Sure, we ship worldwide."},
            headers=auth_headers,
        )
        assert resp.status_code == 204
        assert mock_bot == [{"token": "123456:FAKEBOTTOKEN", "chat_id": 999, "text": "Sure, we ship worldwide."}]

        detail = await client.get(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}", headers=auth_headers
        )
        body = detail.json()
        assert body["status"] == "open_human"
        assert body["messages"][-1]["sender"] == "owner"
        assert body["messages"][-1]["content"] == "Sure, we ship worldwide."

    async def test_reply_without_connected_bot_is_400(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, mock_bot
    ):
        workspace = await _create_workspace(client, auth_headers)
        dialog = await _create_dialog(db_session, workspace["id"])

        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/reply",
            json={"content": "Hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert mock_bot == []  # до Telegram дело не дошло

    async def test_reply_telegram_failure_does_not_save_message(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, mock_bot_failing
    ):
        workspace = await _create_workspace(client, auth_headers)
        await _set_bot_token(db_session, workspace["id"])
        dialog = await _create_dialog(db_session, workspace["id"])

        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/reply",
            json={"content": "Hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 502

        detail = await client.get(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}", headers=auth_headers
        )
        body = detail.json()
        assert body["messages"] == []
        assert body["status"] == "open_auto"

    async def test_reply_content_too_long_is_422(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, mock_bot
    ):
        workspace = await _create_workspace(client, auth_headers)
        await _set_bot_token(db_session, workspace["id"])
        dialog = await _create_dialog(db_session, workspace["id"])

        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/reply",
            json={"content": "x" * 4001},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert mock_bot == []

    async def test_reply_other_users_workspace_is_404(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, other_auth_headers: dict, mock_bot
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        await _set_bot_token(db_session, their_workspace["id"])
        dialog = await _create_dialog(db_session, their_workspace["id"])

        resp = await client.post(
            f"/workspaces/{their_workspace['id']}/dialogs/{dialog.id}/reply",
            json={"content": "Hijack attempt"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert mock_bot == []

    async def test_reply_requires_auth(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, mock_bot
    ):
        workspace = await _create_workspace(client, auth_headers)
        await _set_bot_token(db_session, workspace["id"])
        dialog = await _create_dialog(db_session, workspace["id"])

        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/reply",
            json={"content": "Hello"},
        )
        assert resp.status_code == 401
        assert mock_bot == []


# ---------- close ----------

class TestCloseDialog:
    async def test_close_success(self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        dialog = await _create_dialog(db_session, workspace["id"])

        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/close", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    async def test_close_already_closed_dialog_is_idempotent(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict
    ):
        workspace = await _create_workspace(client, auth_headers)
        dialog = await _create_dialog(db_session, workspace["id"])
        repo = DialogRepository(db_session)
        await repo.set_status(dialog, DialogStatus.CLOSED)

        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/close", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    async def test_close_other_users_workspace_is_404(
        self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict, other_auth_headers: dict
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        dialog = await _create_dialog(db_session, their_workspace["id"])

        resp = await client.post(
            f"/workspaces/{their_workspace['id']}/dialogs/{dialog.id}/close", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_close_nonexistent_dialog_is_404(self, client: AsyncClient, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.post(
            f"/workspaces/{workspace['id']}/dialogs/{fake_id}/close", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_close_requires_auth(self, client: AsyncClient, db_session: AsyncSession, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        dialog = await _create_dialog(db_session, workspace["id"])

        resp = await client.post(f"/workspaces/{workspace['id']}/dialogs/{dialog.id}/close")
        assert resp.status_code == 401