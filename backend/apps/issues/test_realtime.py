"""Tests for committed project-board event delivery through Channels."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.projects.services import create_project
from apps.workspaces.services import create_workspace

from .events import project_group_name
from .services import create_issue, transition_issue


class ProjectEventTests(TransactionTestCase):
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
        self.channel_layer = get_channel_layer()
        self.channel_name = async_to_sync(self.channel_layer.new_channel)("realtime.test")
        async_to_sync(self.channel_layer.group_add)(project_group_name(self.project.id), self.channel_name)

    def tearDown(self):
        async_to_sync(self.channel_layer.group_discard)(project_group_name(self.project.id), self.channel_name)

    def test_issue_creation_publishes_a_committed_project_event(self):
        issue = create_issue(project=self.project, reporter=self.membership, title="Live task")

        event = async_to_sync(self.channel_layer.receive)(self.channel_name)
        self.assertEqual(event["type"], "issue.event")
        self.assertEqual(event["payload"]["event"], "issue.created")
        self.assertEqual(event["payload"]["issue_id"], str(issue.id))

    def test_transition_publishes_new_status(self):
        issue = create_issue(project=self.project, reporter=self.membership, title="Move task")
        async_to_sync(self.channel_layer.receive)(self.channel_name)  # consume issue.created
        target = issue.status.workflow.statuses.get(name="In Progress")

        transition_issue(issue=issue, actor=self.membership, target_status=target)

        event = async_to_sync(self.channel_layer.receive)(self.channel_name)
        self.assertEqual(event["payload"]["event"], "issue.status_changed")
        self.assertEqual(event["payload"]["data"]["status_id"], str(target.id))
