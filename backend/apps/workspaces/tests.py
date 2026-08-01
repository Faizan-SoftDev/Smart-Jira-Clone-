"""Tests for tenant isolation primitives and workspace RBAC."""

from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User

from .models import WorkspaceMembership
from .permissions import WorkspaceAction, can_access_workspace
from .services import create_workspace


class WorkspaceServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="safe-test-password", display_name="Owner"
        )

    def test_creating_workspace_creates_owner_membership(self):
        workspace = create_workspace(owner=self.owner, name="Acme", slug="Acme Workspace")

        membership = WorkspaceMembership.objects.get(workspace=workspace, user=self.owner)
        self.assertEqual(workspace.slug, "acme-workspace")
        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)
        self.assertTrue(
            can_access_workspace(
                user=self.owner, workspace=workspace, action=WorkspaceAction.MANAGE_MEMBERS
            )
        )

    def test_duplicate_slug_does_not_create_a_partial_membership(self):
        create_workspace(owner=self.owner, name="Acme", slug="acme")
        second_owner = User.objects.create_user(
            email="second@example.com", password="safe-test-password", display_name="Second"
        )

        with self.assertRaises(IntegrityError):
            create_workspace(owner=second_owner, name="Other", slug="acme")

        self.assertFalse(WorkspaceMembership.objects.filter(user=second_owner).exists())
