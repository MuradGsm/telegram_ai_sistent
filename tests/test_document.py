from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


# ---------- fixtures ----------

@pytest.fixture
def mock_r2(monkeypatch):
    from app.external.r2_client import r2_client

    upload_mock = AsyncMock()
    delete_mock = AsyncMock()
    monkeypatch.setattr(r2_client, "upload_file", upload_mock)
    monkeypatch.setattr(r2_client, "delete_file", delete_mock)
    return SimpleNamespace(upload=upload_mock, delete=delete_mock)


@pytest.fixture
def mock_arq(monkeypatch):
    from app.services import document_service

    enqueue_mock = AsyncMock()
    fake_redis = SimpleNamespace(enqueue_job=enqueue_mock)

    async def _fake_get_arq_redis():
        return fake_redis

    monkeypatch.setattr(document_service, "get_arq_redis", _fake_get_arq_redis)
    return enqueue_mock


# ---------- helpers ----------

async def _create_workspace(client: AsyncClient, headers: dict, name: str = "Doc Shop") -> dict:
    resp = await client.post("/workspaces", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _upload(
    client: AsyncClient,
    workspace_id: str,
    headers: dict,
    filename: str = "price.pdf",
    content: bytes = b"%PDF-1.4 fake pdf content",
    content_type: str = "application/pdf",
):
    return await client.post(
        f"/workspaces/{workspace_id}/documents",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


# ---------- upload ----------

class TestUploadDocument:
    async def test_upload_pdf_success(self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq):
        workspace = await _create_workspace(client, auth_headers)
        resp = await _upload(client, workspace["id"], auth_headers)

        assert resp.status_code == 201
        body = resp.json()
        assert body["file_name"] == "price.pdf"
        assert body["status"] == "uploaded"
        assert body["chunk_count"] == 0
        mock_r2.upload.assert_called_once()

    async def test_upload_object_key_scoped_to_workspace(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        workspace = await _create_workspace(client, auth_headers)
        await _upload(client, workspace["id"], auth_headers, filename="terms.txt", content_type="text/plain")

        object_key = mock_r2.upload.call_args.args[0]
        assert object_key.startswith(f"{workspace['id']}/")
        assert object_key.endswith("_terms.txt")

    async def test_upload_enqueues_indexing_job(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        workspace = await _create_workspace(client, auth_headers)
        resp = await _upload(client, workspace["id"], auth_headers)
        document_id = resp.json()["id"]

        mock_arq.assert_called_once_with("process_document", document_id)

    async def test_upload_rejects_unsupported_content_type(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        workspace = await _create_workspace(client, auth_headers)
        resp = await _upload(
            client, workspace["id"], auth_headers, filename="cat.png", content_type="image/png"
        )
        assert resp.status_code == 400
        mock_r2.upload.assert_not_called()

    async def test_upload_rejects_oversized_file(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        workspace = await _create_workspace(client, auth_headers)
        oversized = b"a" * (MAX_FILE_SIZE_BYTES + 1)
        resp = await _upload(client, workspace["id"], auth_headers, content=oversized)
        assert resp.status_code == 413
        mock_r2.upload.assert_not_called()

    async def test_upload_requires_auth(self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq):
        workspace = await _create_workspace(client, auth_headers)
        resp = await client.post(
            f"/workspaces/{workspace['id']}/documents",
            files={"file": ("price.pdf", b"data", "application/pdf")},
        )
        assert resp.status_code == 401
        mock_r2.upload.assert_not_called()

    async def test_upload_to_other_users_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict, mock_r2, mock_arq
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        resp = await _upload(client, their_workspace["id"], auth_headers)
        assert resp.status_code == 404
        mock_r2.upload.assert_not_called()

    async def test_upload_to_nonexistent_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await _upload(client, fake_id, auth_headers)
        assert resp.status_code == 404


# ---------- list ----------

class TestListDocuments:
    async def test_list_returns_uploaded_documents(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        workspace = await _create_workspace(client, auth_headers)
        await _upload(client, workspace["id"], auth_headers, filename="a.pdf")
        await _upload(client, workspace["id"], auth_headers, filename="b.pdf")

        resp = await client.get(f"/workspaces/{workspace['id']}/documents", headers=auth_headers)
        assert resp.status_code == 200
        names = {d["file_name"] for d in resp.json()}
        assert names == {"a.pdf", "b.pdf"}

    async def test_list_empty_workspace(self, client: AsyncClient, auth_headers: dict):
        workspace = await _create_workspace(client, auth_headers)
        resp = await client.get(f"/workspaces/{workspace['id']}/documents", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_other_users_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        resp = await client.get(f"/workspaces/{their_workspace['id']}/documents", headers=auth_headers)
        assert resp.status_code == 404


# ---------- delete ----------

class TestDeleteDocument:
    async def test_delete_success(self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq):
        workspace = await _create_workspace(client, auth_headers)
        upload_resp = await _upload(client, workspace["id"], auth_headers)
        document_id = upload_resp.json()["id"]

        resp = await client.delete(
            f"/workspaces/{workspace['id']}/documents/{document_id}", headers=auth_headers
        )
        assert resp.status_code == 204
        mock_r2.delete.assert_called_once()

        list_resp = await client.get(f"/workspaces/{workspace['id']}/documents", headers=auth_headers)
        assert list_resp.json() == []

    async def test_delete_nonexistent_document_is_404(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        workspace = await _create_workspace(client, auth_headers)
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.delete(
            f"/workspaces/{workspace['id']}/documents/{fake_id}", headers=auth_headers
        )
        assert resp.status_code == 404
        mock_r2.delete.assert_not_called()

    async def test_delete_document_from_other_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq
    ):
        workspace_a = await _create_workspace(client, auth_headers, "Workspace A")
        workspace_b = await _create_workspace(client, auth_headers, "Workspace B")
        upload_resp = await _upload(client, workspace_a["id"], auth_headers)
        document_id = upload_resp.json()["id"]

        resp = await client.delete(
            f"/workspaces/{workspace_b['id']}/documents/{document_id}", headers=auth_headers
        )
        assert resp.status_code == 404
        mock_r2.delete.assert_not_called()

        # документ по-прежнему на месте в своём воркспейсе
        still_there = await client.get(
            f"/workspaces/{workspace_a['id']}/documents", headers=auth_headers
        )
        assert len(still_there.json()) == 1

    async def test_delete_document_in_other_users_workspace_is_404(
        self, client: AsyncClient, auth_headers: dict, other_auth_headers: dict, mock_r2, mock_arq
    ):
        their_workspace = await _create_workspace(client, other_auth_headers, "Not Yours")
        upload_resp = await _upload(client, their_workspace["id"], other_auth_headers)
        document_id = upload_resp.json()["id"]

        resp = await client.delete(
            f"/workspaces/{their_workspace['id']}/documents/{document_id}", headers=auth_headers
        )
        assert resp.status_code == 404
        mock_r2.delete.assert_not_called()

    async def test_delete_requires_auth(self, client: AsyncClient, auth_headers: dict, mock_r2, mock_arq):
        workspace = await _create_workspace(client, auth_headers)
        upload_resp = await _upload(client, workspace["id"], auth_headers)
        document_id = upload_resp.json()["id"]

        resp = await client.delete(f"/workspaces/{workspace['id']}/documents/{document_id}")
        assert resp.status_code == 401
        mock_r2.delete.assert_not_called()