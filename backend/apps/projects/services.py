"""Project domain use cases, with tenant checks before database writes."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.workspaces.models import Workspace, WorkspaceMembership

from .models import Project, ProjectMembership, ProjectSettings, Team, TeamMembership
from .models import Sprint, SprintBurndownSnapshot


def create_team(*, workspace: Workspace, name: str, description: str = "") -> Team:
    """Create a workspace-local team; its uniqueness is database enforced."""
    return Team.objects.create(workspace=workspace, name=name.strip(), description=description.strip())


def add_team_member(*, team: Team, membership: WorkspaceMembership) -> TeamMembership:
    """Add an existing member only when it belongs to the team's workspace."""
    if membership.workspace_id != team.workspace_id:
        raise ValueError("Cannot add a member from another workspace to this team.")
    return TeamMembership.objects.create(team=team, workspace_membership=membership)


def create_project(
    *,
    workspace: Workspace,
    lead: WorkspaceMembership,
    name: str,
    key: str,
    slug: str,
    methodology: str = Project.Methodology.KANBAN,
    team: Team | None = None,
) -> Project:
    """Create a project, lead membership, and settings atomically.

    The function rejects cross-tenant references before saving, preventing a
    foreign key from another workspace being attached to this project's data.
    """
    if lead.workspace_id != workspace.id:
        raise ValueError("Project lead must belong to the selected workspace.")
    if team and team.workspace_id != workspace.id:
        raise ValueError("Project team must belong to the selected workspace.")

    normalized_slug = slugify(slug)
    if not normalized_slug:
        raise ValueError("Project slug must contain letters or numbers.")

    with transaction.atomic():
        project = Project.objects.create(
            workspace=workspace,
            team=team,
            lead=lead,
            name=name.strip(),
            key=key.strip().upper(),
            slug=normalized_slug,
            methodology=methodology,
        )
        ProjectMembership.objects.create(
            project=project, workspace_membership=lead, role=ProjectMembership.Role.LEAD
        )
        ProjectSettings.objects.create(project=project)
    return project


def create_sprint(*, project: Project, name: str, goal: str = "", start_date=None, end_date=None) -> Sprint:
    """Create a planned sprint; only the project-level service can activate it."""
    return Sprint.objects.create(
        project=project, name=name.strip(), goal=goal.strip(), start_date=start_date, end_date=end_date
    )


def start_sprint(*, sprint: Sprint) -> Sprint:
    """Activate one sprint atomically; the partial unique constraint backs this rule."""
    with transaction.atomic():
        Sprint.objects.select_for_update().filter(project=sprint.project, status=Sprint.Status.ACTIVE).exclude(pk=sprint.pk).update(status=Sprint.Status.COMPLETED, completed_at=timezone.now())
        sprint.status = Sprint.Status.ACTIVE
        sprint.save(update_fields=["status"])
    return sprint


def assign_issue_to_sprint(*, sprint: Sprint, issue) -> None:
    """Put an issue in a sprint only when both aggregates share the same project."""
    if issue.project_id != sprint.project_id:
        raise ValueError("Issue and sprint must belong to the same project.")
    issue.sprint = sprint
    issue.save(update_fields=["sprint", "updated_at"])


def record_burndown_snapshot(*, sprint: Sprint) -> SprintBurndownSnapshot:
    """Store today's remaining non-done story points for reporting and charts."""
    from apps.issues.models import Issue

    remaining = sum(
        issue.story_points or 0
        for issue in Issue.objects.filter(sprint=sprint).exclude(status__category="done")
    )
    snapshot, _ = SprintBurndownSnapshot.objects.update_or_create(
        sprint=sprint, date=timezone.localdate(), defaults={"remaining_points": remaining}
    )
    return snapshot


def complete_sprint(*, sprint: Sprint) -> Sprint:
    """Capture final burndown data then close an active sprint."""
    if sprint.status != Sprint.Status.ACTIVE:
        raise ValueError("Only an active sprint can be completed.")
    with transaction.atomic():
        record_burndown_snapshot(sprint=sprint)
        sprint.status = Sprint.Status.COMPLETED
        sprint.completed_at = timezone.now()
        sprint.save(update_fields=["status", "completed_at"])
    return sprint
