"""Tests for project isolation, defaults, and RBAC foundations."""

from django.test import TestCase

from apps.accounts.models import User
from apps.workspaces.services import create_workspace

from .models import ProjectMembership, TeamMembership
from .permissions import ProjectAction, can_access_project
from .services import add_team_member, create_project, create_team


class ProjectServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="safe-test-password", display_name="Owner"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="safe-test-password", display_name="Other"
        )
        self.workspace = create_workspace(owner=self.owner, name="Acme", slug="acme")
        self.other_workspace = create_workspace(
            owner=self.other_user, name="Other", slug="other"
        )
        self.owner_membership = self.workspace.memberships.get(user=self.owner)
        self.other_membership = self.other_workspace.memberships.get(user=self.other_user)

    def test_project_creation_builds_lead_membership_and_default_settings(self):
        team = create_team(workspace=self.workspace, name="Platform")
        project = create_project(
            workspace=self.workspace,
            lead=self.owner_membership,
            team=team,
            name="TaskCraft API",
            key="tc",
            slug="TaskCraft API",
            methodology="scrum",
        )

        self.assertEqual(project.key, "TC")
        self.assertEqual(project.slug, "taskcraft-api")
        self.assertEqual(project.settings.default_estimate_unit, "points")
        self.assertEqual(
            project.memberships.get(workspace_membership=self.owner_membership).role,
            ProjectMembership.Role.LEAD,
        )
        self.assertTrue(
            can_access_project(user=self.owner, project=project, action=ProjectAction.MANAGE)
        )

    def test_cross_workspace_lead_or_team_is_rejected_before_save(self):
        local_team = create_team(workspace=self.workspace, name="Platform")

        with self.assertRaisesRegex(ValueError, "lead"):
            create_project(
                workspace=self.workspace,
                lead=self.other_membership,
                name="Invalid lead",
                key="BAD",
                slug="invalid-lead",
            )

        with self.assertRaisesRegex(ValueError, "team"):
            create_project(
                workspace=self.other_workspace,
                lead=self.other_membership,
                team=local_team,
                name="Invalid team",
                key="BAD",
                slug="invalid-team",
            )

    def test_team_rejects_member_from_another_workspace(self):
        team = create_team(workspace=self.workspace, name="Platform")

        with self.assertRaisesRegex(ValueError, "another workspace"):
            add_team_member(team=team, membership=self.other_membership)

        membership = add_team_member(team=team, membership=self.owner_membership)
        self.assertIsInstance(membership, TeamMembership)
