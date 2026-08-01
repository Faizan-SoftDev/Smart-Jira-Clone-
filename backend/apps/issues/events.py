"""Project-scoped real-time events emitted only after database commit."""

from __future__ import annotations

from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone


def project_group_name(project_id: object) -> str:
    """Return a stable Channels group name for one project's live board."""
    return f"project_{project_id}"


def broadcast_project_event(*, project_id: object, event_type: str, issue_id: object, data: dict[str, Any] | None = None) -> None:
    """Publish a compact event after commit so clients never observe rolled-back state."""
    payload = {
        "event": event_type,
        "project_id": str(project_id),
        "issue_id": str(issue_id),
        "data": data or {},
        "occurred_at": timezone.now().isoformat(),
    }

    def publish() -> None:
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                project_group_name(project_id), {"type": "issue.event", "payload": payload}
            )

    transaction.on_commit(publish)
