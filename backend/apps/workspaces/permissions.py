"""Workspace-scoped authorization policies used by APIs and services."""

from __future__ import annotations

from enum import StrEnum

from apps.accounts.models import User

from .models import Workspace, WorkspaceMembership


class WorkspaceAction(StrEnum):
    """Stable action names for workspace-level authorization checks."""

    VIEW = "view"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_WORKSPACE = "manage_workspace"


ROLE_ACTIONS: dict[str, frozenset[WorkspaceAction]] = {
    WorkspaceMembership.Role.OWNER: frozenset(WorkspaceAction),
    WorkspaceMembership.Role.ADMIN: frozenset(WorkspaceAction),
    WorkspaceMembership.Role.PROJECT_LEAD: frozenset({WorkspaceAction.VIEW}),
    WorkspaceMembership.Role.DEVELOPER: frozenset({WorkspaceAction.VIEW}),
    WorkspaceMembership.Role.VIEWER: frozenset({WorkspaceAction.VIEW}),
    WorkspaceMembership.Role.EXTERNAL_CLIENT: frozenset({WorkspaceAction.VIEW}),
}


def can_access_workspace(*, user: User, workspace: Workspace, action: WorkspaceAction) -> bool:
    """Return whether a user has a workspace role granting ``action``.

    This is a single indexed ``EXISTS`` query. Platform superusers are allowed
    for support and administrative recovery; normal users require membership.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    allowed_roles = [role for role, actions in ROLE_ACTIONS.items() if action in actions]
    return WorkspaceMembership.objects.filter(
        workspace=workspace, user=user, role__in=allowed_roles
    ).exists()
