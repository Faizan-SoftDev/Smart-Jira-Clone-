"""Workspace API routing."""

from django.urls import path

from .api import WorkspaceDeletionRequestView, WorkspaceExportView, WorkspaceListCreateView

urlpatterns = [
    path("workspaces/", WorkspaceListCreateView.as_view(), name="workspace-list-create"),
    path("workspaces/<uuid:workspace_id>/export/", WorkspaceExportView.as_view(), name="workspace-export"),
    path("workspaces/<uuid:workspace_id>/deletion-request/", WorkspaceDeletionRequestView.as_view(), name="workspace-deletion-request"),
]
