"""WebSocket routing for issue collaboration."""

from django.urls import path

from .consumers import ProjectBoardConsumer

websocket_urlpatterns = [
    path("ws/projects/<uuid:project_id>/board/", ProjectBoardConsumer.as_asgi(), name="project-board-ws"),
]
