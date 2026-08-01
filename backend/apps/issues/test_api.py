"""End-to-end REST tests for scope enforcement and issue commands."""

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.services import create_project
from apps.workspaces.services import create_workspace

from .services import create_issue


class ProjectApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="safe-test-password", display_name="Owner"
        )
        self.outsider = User.objects.create_user(
            email="outsider@example.com", password="safe-test-password", display_name="Outsider"
        )
        self.workspace = create_workspace(owner=self.owner, name="Acme", slug="acme")
        self.owner_membership = self.workspace.memberships.get(user=self.owner)
        self.project = create_project(
            workspace=self.workspace,
            lead=self.owner_membership,
            name="TaskCraft API",
            key="TC",
            slug="taskcraft-api",
        )
        self.client.force_authenticate(self.owner)

    def test_workspace_list_is_membership_scoped(self):
        response = self.client.get(reverse("workspace-list-create"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data], [str(self.workspace.id)])

    def test_workspace_admin_can_create_and_list_a_project(self):
        create_url = reverse("project-list-create", kwargs={"workspace_id": self.workspace.id})
        response = self.client.post(
            create_url,
            {"name": "Web app", "key": "WEB", "slug": "web-app", "methodology": "kanban"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["key"], "WEB")
        listing = self.client.get(create_url)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 2)

    def test_outsider_cannot_list_workspace_projects(self):
        self.client.force_authenticate(self.outsider)

        response = self.client.get(
            reverse("project-list-create", kwargs={"workspace_id": self.workspace.id})
        )

        self.assertEqual(response.status_code, 403)


class IssueApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="safe-test-password", display_name="Owner"
        )
        self.workspace = create_workspace(owner=self.owner, name="Acme", slug="acme")
        self.membership = self.workspace.memberships.get(user=self.owner)
        self.project = create_project(
            workspace=self.workspace,
            lead=self.membership,
            name="TaskCraft API",
            key="TC",
            slug="taskcraft-api",
        )
        self.client.force_authenticate(self.owner)

    def test_issue_endpoint_creates_paginates_and_transitions(self):
        list_url = reverse("issue-list-create", kwargs={"project_id": self.project.id})
        created = self.client.post(list_url, {"title": "Document API"}, format="json")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["key"], "TC-1")
        comment = self.client.post(
            reverse("issue-comment-list-create", kwargs={"issue_id": created.data["id"]}),
            {"body": "Initial **Markdown** discussion."},
            format="json",
        )
        self.assertEqual(comment.status_code, 201)
        self.assertEqual(comment.data["body"], "Initial **Markdown** discussion.")
        issue = create_issue(project=self.project, reporter=self.membership, title="Second")
        listed = self.client.get(list_url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["count"], 2)

        workflow = issue.status.workflow
        in_progress = workflow.statuses.get(name="In Progress")
        transition = self.client.post(
            reverse("issue-transition", kwargs={"issue_id": issue.id}),
            {"target_status_id": str(in_progress.id)},
            format="json",
        )
        self.assertEqual(transition.status_code, 200)
        self.assertEqual(str(transition.data["status"]), str(in_progress.id))
