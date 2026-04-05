from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from uxray_fetch.models import BridgeEvent


class WebSocketEventBridge:
    def __init__(self, host: str, port: int, enabled: bool) -> None:
        self.host = host
        self.port = port
        self.enabled = enabled
        self.history: deque[BridgeEvent] = deque(maxlen=200)
        self._server: Any | None = None
        self._subscribers: set[asyncio.Queue[str]] = set()

    async def start(self) -> None:
        if not self.enabled or self._server is not None:
            return
        import websockets

        async def handler(connection) -> None:
            queue: asyncio.Queue[str] = asyncio.Queue()
            self._subscribers.add(queue)
            try:
                while True:
                    payload = await queue.get()
                    await connection.send(payload)
            finally:
                self._subscribers.discard(queue)

        self._server = await websockets.serve(handler, self.host, self.port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def emit(self, event: BridgeEvent) -> None:
        self.history.append(event)
        if not self.enabled:
            return
        payload = event.model_dump_json()
        dead_queues: list[asyncio.Queue[str]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(payload)
            except RuntimeError:
                dead_queues.append(queue)
        for queue in dead_queues:
            self._subscribers.discard(queue)
