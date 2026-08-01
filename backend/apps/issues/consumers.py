"""Authenticated WebSocket consumer for project board updates."""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.projects.models import Project
from apps.projects.permissions import ProjectAction, can_access_project

from .events import project_group_name


class ProjectBoardConsumer(AsyncJsonWebsocketConsumer):
    """Stream compact issue events to authenticated viewers of one project."""

    async def connect(self) -> None:
        self.project_id = self.scope["url_route"]["kwargs"]["project_id"]
        if not await self._can_view_project():
            await self.close(code=4403)
            return
        self.group_name = project_group_name(self.project_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs) -> None:
        """Keep the socket server-driven; client writes remain authenticated HTTP commands."""
        await self.send_json({"event": "error", "data": {"detail": "Client messages are not supported."}})

    async def issue_event(self, event) -> None:
        """Forward server-side committed event payloads to the connected board."""
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _can_view_project(self) -> bool:
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return False
        try:
            project = Project.objects.select_related("workspace").get(pk=self.project_id)
        except Project.DoesNotExist:
            return False
        return can_access_project(user=user, project=project, action=ProjectAction.VIEW)
