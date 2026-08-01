"""Tests for issue numbering, workflow state transitions, and tenant isolation."""

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.projects.services import create_project
from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.services import create_workspace

from .filters import apply_jql_lite
from .models import Issue, IssueActivity, Notification, WorkflowStatus
from .services import add_attachment, add_comment, create_custom_field, create_issue, create_saved_filter, move_issue_on_board, transition_issue


class IssueServiceTests(TestCase):
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
        self.project = create_project(
            workspace=self.workspace,
            lead=self.owner_membership,
            name="TaskCraft API",
            key="TC",
            slug="taskcraft-api",
        )

    def test_issue_creation_sets_default_workflow_and_sequential_keys(self):
        first = create_issue(project=self.project, reporter=self.owner_membership, title="First task")
        second = create_issue(project=self.project, reporter=self.owner_membership, title="Second task")

        self.assertEqual((first.key, second.key), ("TC-1", "TC-2"))
        self.assertEqual(first.status.name, "To Do")
        self.assertTrue(self.project.workflows.get(is_default=True).transitions.exists())

    def test_only_configured_workflow_transitions_are_permitted(self):
        issue = create_issue(project=self.project, reporter=self.owner_membership, title="Ship workflow")
        workflow = issue.status.workflow
        in_progress = workflow.statuses.get(category=WorkflowStatus.Category.IN_PROGRESS)
        done = workflow.statuses.get(category=WorkflowStatus.Category.DONE)

        transition_issue(issue=issue, actor=self.owner_membership, target_status=in_progress)
        issue.refresh_from_db()
        self.assertEqual(issue.status, in_progress)

        transition_issue(issue=issue, actor=self.owner_membership, target_status=done)
        issue.refresh_from_db()
        self.assertEqual(issue.status, done)

        with self.assertRaisesRegex(ValueError, "not permitted"):
            transition_issue(issue=issue, actor=self.owner_membership, target_status=in_progress)

    def test_cross_tenant_reporter_and_parent_are_rejected(self):
        parent = create_issue(project=self.project, reporter=self.owner_membership, title="Parent")

        with self.assertRaisesRegex(PermissionError, "permission"):
            create_issue(project=self.project, reporter=self.other_membership, title="No access")

        other_project = create_project(
            workspace=self.other_workspace,
            lead=self.other_membership,
            name="Other API",
            key="OTH",
            slug="other-api",
        )
        with self.assertRaisesRegex(ValueError, "Parent issue"):
            create_issue(
                project=other_project,
                reporter=self.other_membership,
                title="Invalid subtask",
                issue_type=Issue.Type.SUBTASK,
                parent=parent,
            )

    def test_comment_mentions_notify_members_and_create_audit_activity(self):
        colleague = User.objects.create_user(
            email="colleague@example.com", password="safe-test-password", display_name="Colleague"
        )
        colleague_membership = WorkspaceMembership.objects.create(
            workspace=self.workspace, user=colleague, role=WorkspaceMembership.Role.DEVELOPER
        )
        issue = create_issue(project=self.project, reporter=self.owner_membership, title="Discuss API")

        comment = add_comment(
            issue=issue,
            author=self.owner_membership,
            body="Please review this @colleague@example.com.",
        )

        self.assertEqual(comment.mentions.get().membership, colleague_membership)
        self.assertEqual(Notification.objects.get(comment=comment).recipient, colleague_membership)
        self.assertTrue(
            IssueActivity.objects.filter(issue=issue, event_type=IssueActivity.Event.COMMENTED).exists()
        )

    def test_attachment_is_pending_and_recorded_in_activity(self):
        issue = create_issue(project=self.project, reporter=self.owner_membership, title="Attach brief")
        uploaded = SimpleUploadedFile("brief.txt", b"Project brief", content_type="text/plain")

        attachment = add_attachment(issue=issue, uploader=self.owner_membership, uploaded_file=uploaded)

        self.assertEqual(attachment.scan_status, attachment.ScanStatus.PENDING)
        self.assertTrue(
            IssueActivity.objects.filter(issue=issue, event_type=IssueActivity.Event.ATTACHMENT_ADDED).exists()
        )
        attachment.file.delete(save=False)

    def test_custom_fields_and_jql_lite_are_project_scoped(self):
        create_custom_field(
            project=self.project,
            name="Customer tier",
            key="customer-tier",
            field_type="select",
            configuration={"choices": ["gold", "silver"]},
        )
        issue = create_issue(
            project=self.project,
            reporter=self.owner_membership,
            title="Priority customer defect",
            issue_type=Issue.Type.BUG,
            priority=Issue.Priority.HIGH,
            custom_fields={"customer-tier": "gold"},
        )
        self.assertEqual(issue.custom_values.get().value, "gold")

        results = apply_jql_lite(Issue.objects.filter(project=self.project), "priority = high AND type = bug")
        self.assertEqual(list(results), [issue])
        saved = create_saved_filter(
            project=self.project,
            owner=self.owner_membership,
            name="High priority bugs",
            jql="priority = high AND type = bug",
        )
        self.assertEqual(saved.project, self.project)

    def test_board_move_reorders_a_column(self):
        first = create_issue(project=self.project, reporter=self.owner_membership, title="First")
        second = create_issue(project=self.project, reporter=self.owner_membership, title="Second")

        move_issue_on_board(
            issue=second, actor=self.owner_membership, target_status=first.status, before_issue=first
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertLess(second.board_order, first.board_order)
