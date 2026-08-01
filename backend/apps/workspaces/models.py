"""Tenant boundary and role assignments for TaskCraft."""

from __future__ import annotations

import uuid
import secrets

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


workspace_slug_validator = RegexValidator(
    regex=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    message="Use lowercase letters, numbers, and single hyphens only.",
)


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


class Workspace(models.Model):
    """An isolated organization and root of all tenant-owned resources."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=80, unique=True, validators=[workspace_slug_validator])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class WorkspaceMembership(models.Model):
    """A user's workspace-scoped role; never use global roles for tenant access."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        PROJECT_LEAD = "project_lead", "Project lead"
        DEVELOPER = "developer", "Developer"
        VIEWER = "viewer", "Viewer"
        EXTERNAL_CLIENT = "external_client", "External client"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.VIEWER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="unique_workspace_membership"),
        ]
        indexes = [
            models.Index(fields=["workspace", "role"], name="workspace_role_idx"),
            models.Index(fields=["user", "workspace"], name="user_workspace_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.workspace} ({self.role})"


class WorkspaceDeletionRequest(models.Model):
    """Auditable, owner-initiated deletion request processed by a background worker."""

    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, related_name="deletion_request")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)


class WorkspaceInvitation(models.Model):
    """Pending workspace seat invitation, redeemable once by its email recipient."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=24, choices=WorkspaceMembership.Role.choices, default=WorkspaceMembership.Role.VIEWER)
    token = models.CharField(max_length=64, unique=True, default=generate_invitation_token)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_invitations")
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "email"], name="unique_pending_workspace_invitation")]
