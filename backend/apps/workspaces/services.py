"""Workspace use cases. Views and API serializers call these functions."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from apps.accounts.models import User

from .models import Workspace, WorkspaceMembership


def create_workspace(*, owner: User, name: str, slug: str) -> Workspace:
    """Create a workspace and its owner membership as one atomic operation.

    The database unique constraint remains the authoritative concurrency guard
    for slugs. Callers can translate ``IntegrityError`` into a validation error.
    """
    normalized_slug = slugify(slug)
    if not normalized_slug:
        raise ValueError("Workspace slug must contain letters or numbers.")

    try:
        with transaction.atomic():
            workspace = Workspace.objects.create(
                name=name.strip(), slug=normalized_slug, created_by=owner
            )
            WorkspaceMembership.objects.create(
                workspace=workspace,
                user=owner,
                role=WorkspaceMembership.Role.OWNER,
            )
    except IntegrityError:
        # Preserve the database exception for API code that needs conflict details.
        raise
    return workspace
