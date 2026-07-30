"""WebSocket delivery of real-time Kanban status updates."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.domain.models.task import TaskStatus
from app.infrastructure.database.models import UserModel
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.security import decode_access_token

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Concurrency-safe registry and broadcaster for Kanban WebSocket clients."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._connections_lock = asyncio.Lock()
        self._broadcast_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and retain a WebSocket connection."""
        await websocket.accept()
        async with self._connections_lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a closed or failed WebSocket connection."""
        async with self._connections_lock:
            self._connections.discard(websocket)

    async def connection_count(self) -> int:
        """Return the number of currently connected clients."""
        async with self._connections_lock:
            return len(self._connections)

    async def broadcast_task_status_change(
        self,
        *,
        task_id: UUID,
        previous_status: TaskStatus,
        status: TaskStatus,
        occurred_at: datetime | None = None,
    ) -> None:
        """Broadcast a status transition and drop clients that cannot receive it."""
        await self.broadcast({
            "event": "task.status_changed",
            "task_id": str(task_id),
            "previous_status": previous_status.value,
            "status": status.value,
            "occurred_at": (occurred_at or datetime.now(timezone.utc)).isoformat(),
        })

    async def broadcast_task_created(self, *, task_id: UUID, occurred_at: datetime | None = None) -> None:
        """Notify Kanban clients to refresh after a new task is persisted."""
        await self.broadcast({
            "event": "task.created",
            "task_id": str(task_id),
            "occurred_at": (occurred_at or datetime.now(timezone.utc)).isoformat(),
        })

    async def broadcast(self, event: dict[str, str]) -> None:
        """Broadcast a JSON-compatible event and remove broken connections."""
        async with self._broadcast_lock:
            async with self._connections_lock:
                connections = tuple(self._connections)
            if not connections:
                return
            results = await asyncio.gather(
                *(connection.send_json(event) for connection in connections),
                return_exceptions=True,
            )
            failed_connections = {
                connection
                for connection, result in zip(connections, results, strict=True)
                if isinstance(result, BaseException)
            }
            if failed_connections:
                async with self._connections_lock:
                    self._connections.difference_update(failed_connections)


class RedisConnectionManager(ConnectionManager):
    """Local WebSocket fan-out backed by Redis Pub/Sub across API replicas."""

    def __init__(self, redis_url: str | None = None, channel: str = "smart-jira:kanban") -> None:
        super().__init__()
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._channel = channel
        self._redis = None
        self._listener: asyncio.Task[None] | None = None
        self._instance_id = os.urandom(8).hex()

    async def start(self) -> None:
        """Connect to Redis and start receiving events published by other replicas."""
        if self._listener is not None:
            return
        try:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
            self._listener = asyncio.create_task(self._listen(), name="kanban-redis-listener")
        except Exception:
            logger.warning("Redis unavailable; Kanban sync is local to this API replica", exc_info=True)
            if self._redis is not None:
                await self._redis.aclose()
            self._redis = None

    async def stop(self) -> None:
        """Stop the subscriber before closing the Redis client."""
        if self._listener is not None:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
            self._listener = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def broadcast(self, event: dict[str, str]) -> None:
        await super().broadcast(event)
        if self._redis is not None:
            try:
                await self._redis.publish(self._channel, json.dumps({"origin": self._instance_id, "event": event}))
            except Exception:
                logger.exception("Unable to publish Kanban event to Redis")

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                envelope = json.loads(message["data"])
                event = envelope.get("event")
                if envelope.get("origin") != self._instance_id and isinstance(event, dict):
                    await super().broadcast(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis Kanban subscriber stopped unexpectedly")
        finally:
            await pubsub.aclose()


kanban_sync_manager = RedisConnectionManager()
kanban_router = APIRouter(tags=["kanban-sync"])


@kanban_router.websocket("/ws/kanban")
async def kanban_websocket(websocket: WebSocket) -> None:
    """Keep an authenticated client connected to receive Kanban events."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        claims = decode_access_token(token)
        with SessionLocal() as session:
            user = session.get(UserModel, claims["sub"])
            if user is None or not user.is_active or user.role.value != claims["role"]:
                raise ValueError("inactive or invalid user")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await kanban_sync_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await kanban_sync_manager.disconnect(websocket)
    except Exception:
        await kanban_sync_manager.disconnect(websocket)
        raise
