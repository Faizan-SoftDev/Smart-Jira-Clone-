"""Tenant-scoped teams, projects, and their access configuration."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from apps.workspaces.models import Workspace, WorkspaceMembership


project_key_validator = RegexValidator(
    regex=r"^[A-Z][A-Z0-9]{1,9}$",
    message="Project key must be 2-10 uppercase letters or numbers and start with a letter.",
)


class Team(models.Model):
    """A workspace-local group responsible for one or more projects."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "name"], name="unique_team_name_per_workspace"),
        ]

    def __str__(self) -> str:
        return self.name


class TeamMembership(models.Model):
    """Links a workspace member to a team without duplicating user identity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    workspace_membership = models.ForeignKey(
        WorkspaceMembership, on_delete=models.CASCADE, related_name="team_memberships"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "workspace_membership"], name="unique_team_membership"),
        ]

    def clean(self) -> None:
        if self.team_id and self.workspace_membership_id and self.team.workspace_id != self.workspace_membership.workspace_id:
            raise ValidationError("A team member must belong to the team's workspace.")


class Project(models.Model):
    """A board and workflow container, always isolated to one workspace."""

    class Methodology(models.TextChoices):
        KANBAN = "kanban", "Kanban"
        SCRUM = "scrum", "Scrum"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="projects")
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    name = models.CharField(max_length=150)
    key = models.CharField(max_length=10, validators=[project_key_validator])
    slug = models.SlugField(max_length=100)
    methodology = models.CharField(max_length=10, choices=Methodology.choices, default=Methodology.KANBAN)
    lead = models.ForeignKey(
        WorkspaceMembership, on_delete=models.PROTECT, related_name="led_projects"
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "key"], name="unique_project_key_per_workspace"),
            models.UniqueConstraint(fields=["workspace", "slug"], name="unique_project_slug_per_workspace"),
        ]
        indexes = [
            models.Index(fields=["workspace", "is_archived", "updated_at"], name="project_workspace_active_idx"),
        ]

    def clean(self) -> None:
        errors = {}
        if self.team_id and self.team.workspace_id != self.workspace_id:
            errors["team"] = "A project team must belong to the project's workspace."
        if self.lead_id and self.lead.workspace_id != self.workspace_id:
            errors["lead"] = "A project lead must belong to the project's workspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.key}: {self.name}"


class ProjectMembership(models.Model):
    """Optional project-level role assigned to an existing workspace member."""

    class Role(models.TextChoices):
        LEAD = "lead", "Lead"
        CONTRIBUTOR = "contributor", "Contributor"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    workspace_membership = models.ForeignKey(
        WorkspaceMembership, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CONTRIBUTOR)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "workspace_membership"], name="unique_project_membership"),
        ]
        indexes = [models.Index(fields=["project", "role"], name="project_role_idx")]

    def clean(self) -> None:
        if self.project_id and self.workspace_membership_id and self.project.workspace_id != self.workspace_membership.workspace_id:
            raise ValidationError("A project member must belong to the project's workspace.")


class ProjectSettings(models.Model):
    """Small, explicit project configuration before workflows are introduced."""

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="settings")
    allow_unassigned_issues = models.BooleanField(default=True)
    allow_subtasks = models.BooleanField(default=True)
    default_estimate_unit = models.CharField(
        max_length=12,
        choices=[("points", "Story points"), ("hours", "Hours")],
        default="points",
    )
    issue_counter = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"Settings for {self.project}"


class Sprint(models.Model):
    """A time-boxed Scrum iteration owned by exactly one project."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sprints")
    name = models.CharField(max_length=120)
    goal = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project"], condition=Q(status="active"), name="one_active_sprint_per_project"),
            models.UniqueConstraint(fields=["project", "name"], name="unique_sprint_name_per_project"),
        ]

    def clean(self) -> None:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "Sprint end date must not precede start date."})

    def __str__(self) -> str:
        return f"{self.project.key}: {self.name}"


class SprintBurndownSnapshot(models.Model):
    """Daily remaining story points, retained for a lightweight burndown chart."""

    sprint = models.ForeignKey(Sprint, on_delete=models.CASCADE, related_name="burndown_snapshots")
    date = models.DateField()
    remaining_points = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["sprint", "date"], name="unique_sprint_burndown_date")]
