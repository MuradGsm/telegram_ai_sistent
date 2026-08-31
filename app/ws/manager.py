from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket

class DialogConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, dialog_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[dialog_id].add(websocket)

    def disconnect(self, dialog_id: UUID, websocket: WebSocket) -> None:
        conns = self._connections.get(dialog_id)

        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._connections.pop(dialog_id, None)

    async def broadcast(self, dialog_id: UUID, payload: dict) -> None:
        conns = self._connections.get(dialog_id)
        if not conns:
            return
        dead: list[WebSocket] = []
        for ws in list(conns):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(dialog_id, ws)

ws_manager = DialogConnectionManager()
