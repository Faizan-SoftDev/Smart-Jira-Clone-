"""Project-scoped authorization built on the workspace tenant boundary."""

from __future__ import annotations

from enum import StrEnum

from apps.accounts.models import User
from apps.workspaces.models import WorkspaceMembership

from .models import Project, ProjectMembership


class ProjectAction(StrEnum):
    VIEW = "view"
    MANAGE = "manage"


def can_access_project(*, user: User, project: Project, action: ProjectAction) -> bool:
    """Check project access with one membership existence query for each path."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    workspace_roles = [WorkspaceMembership.Role.OWNER, WorkspaceMembership.Role.ADMIN]
    if action is ProjectAction.VIEW:
        workspace_roles.append(WorkspaceMembership.Role.PROJECT_LEAD)
    if WorkspaceMembership.objects.filter(
        workspace=project.workspace, user=user, role__in=workspace_roles
    ).exists():
        return True

    project_roles = [ProjectMembership.Role.LEAD]
    if action is ProjectAction.VIEW:
        project_roles += [ProjectMembership.Role.CONTRIBUTOR, ProjectMembership.Role.VIEWER]
    return ProjectMembership.objects.filter(
        project=project, workspace_membership__user=user, role__in=project_roles
    ).exists()
