from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.enums import ChannelType
from app.db.session import AsyncSessionLocal
from app.models.channel import Channel
from app.repositories.dialog_repository import DialogRepository
from app.services.dialog_service import DialogService
from app.ws.manager import ws_manager

router = APIRouter(tags=["widget"])


@router.websocket("/ws/widget/{channel_id}")
async def widget_websocket(websocket: WebSocket, channel_id: UUID, visitor_id: str):
    async with AsyncSessionLocal() as db:
        channel = await db.get(Channel, channel_id)
        if channel is None or channel.type != ChannelType.WEB:
            await websocket.close(code=4404)
            return

        allowed_origin = channel.credentials.get("allowed_origin")
        origin = websocket.headers.get("origin")
        if allowed_origin and origin != allowed_origin:
            await websocket.close(code=4403)
            return

        dialog_repo = DialogRepository(db)
        dialog = await dialog_repo.get_or_create(
            workspace_id=channel.workspace_id,
            channel_id=channel.id,
            external_customer_id=visitor_id,
            customer_display_name=None,
        )

    await websocket.accept()
    await ws_manager.connect(dialog.id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            text = payload.get("text")
            if not text:
                continue

            async with AsyncSessionLocal() as db:
                dialog_service = DialogService(db)
                await dialog_service.handle_incoming_customer_message(
                    workspace_id=channel.workspace_id,
                    channel_id=channel.id,
                    external_customer_id=visitor_id,
                    customer_display_name=payload.get("display_name"),
                    text=text,
                )
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(dialog.id, websocket)