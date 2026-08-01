"""Workflow and issue aggregate models, scoped to a single project."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.projects.models import Project
from apps.projects.models import Sprint
from apps.workspaces.models import WorkspaceMembership


class Workflow(models.Model):
    """A project's configurable state machine for issue lifecycle changes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="workflows")
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project"], condition=Q(is_default=True), name="one_default_workflow_per_project"
            ),
            models.UniqueConstraint(fields=["project", "name"], name="unique_workflow_name_per_project"),
        ]

    def __str__(self) -> str:
        return f"{self.project}: {self.name}"


class WorkflowStatus(models.Model):
    """A named state on one workflow, ordered for board presentation."""

    class Category(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="statuses")
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=16, choices=Category.choices)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(fields=["workflow", "name"], name="unique_status_name_per_workflow"),
            models.UniqueConstraint(fields=["workflow", "position"], name="unique_status_position_per_workflow"),
        ]

    def __str__(self) -> str:
        return self.name


class WorkflowTransition(models.Model):
    """An explicit permitted movement from one status to another."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="transitions")
    from_status = models.ForeignKey(
        WorkflowStatus, on_delete=models.CASCADE, related_name="outgoing_transitions"
    )
    to_status = models.ForeignKey(
        WorkflowStatus, on_delete=models.CASCADE, related_name="incoming_transitions"
    )
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "from_status", "to_status"], name="unique_workflow_transition"
            ),
        ]

    def clean(self) -> None:
        if self.from_status_id and self.from_status.workflow_id != self.workflow_id:
            raise ValidationError({"from_status": "Status must belong to this workflow."})
        if self.to_status_id and self.to_status.workflow_id != self.workflow_id:
            raise ValidationError({"to_status": "Status must belong to this workflow."})


class Issue(models.Model):
    """The core project work item with an immutable, sequential issue number."""

    class Type(models.TextChoices):
        EPIC = "epic", "Epic"
        STORY = "story", "Story"
        TASK = "task", "Task"
        BUG = "bug", "Bug"
        SUBTASK = "subtask", "Sub-task"

    class Priority(models.TextChoices):
        LOWEST = "lowest", "Lowest"
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        HIGHEST = "highest", "Highest"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="issues")
    number = models.PositiveIntegerField(editable=False)
    issue_type = models.CharField(max_length=12, choices=Type.choices, default=Type.TASK)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.ForeignKey(WorkflowStatus, on_delete=models.PROTECT, related_name="issues")
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.MEDIUM)
    reporter = models.ForeignKey(
        WorkspaceMembership, on_delete=models.PROTECT, related_name="reported_issues"
    )
    assignee = models.ForeignKey(
        WorkspaceMembership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_issues",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="subtasks"
    )
    labels = models.JSONField(default=list, blank=True)
    story_points = models.PositiveSmallIntegerField(null=True, blank=True)
    sprint = models.ForeignKey(Sprint, on_delete=models.SET_NULL, null=True, blank=True, related_name="issues")
    board_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="unique_issue_number_per_project"),
        ]
        indexes = [
            models.Index(fields=["project", "status", "updated_at"], name="issue_proj_status_updated_idx"),
            models.Index(fields=["project", "issue_type", "updated_at"], name="issue_proj_type_updated_idx"),
            models.Index(fields=["project", "status", "board_order"], name="issue_board_order_idx"),
        ]

    @property
    def key(self) -> str:
        """Return the stable human-facing issue key, for example ``TC-42``."""
        return f"{self.project.key}-{self.number}"

    def clean(self) -> None:
        errors = {}
        if self.status_id and self.status.workflow.project_id != self.project_id:
            errors["status"] = "Issue status must belong to this project."
        if self.reporter_id and self.reporter.workspace_id != self.project.workspace_id:
            errors["reporter"] = "Reporter must belong to the project's workspace."
        if self.assignee_id and self.assignee.workspace_id != self.project.workspace_id:
            errors["assignee"] = "Assignee must belong to the project's workspace."
        if self.parent_id and self.parent.project_id != self.project_id:
            errors["parent"] = "Parent issue must belong to the same project."
        if self.sprint_id and self.sprint.project_id != self.project_id:
            errors["sprint"] = "Sprint must belong to the same project."
        if self.issue_type == self.Type.SUBTASK and not self.parent_id:
            errors["parent"] = "A sub-task requires a parent issue."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.key} {self.title}"


class IssueComment(models.Model):
    """Markdown collaboration message attached to a single issue."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(WorkspaceMembership, on_delete=models.PROTECT, related_name="issue_comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["issue", "created_at"], name="comment_issue_created_idx")]

    def clean(self) -> None:
        if self.author_id and self.author.workspace_id != self.issue.project.workspace_id:
            raise ValidationError("Comment author must belong to the issue workspace.")


class CommentMention(models.Model):
    """A resolved user mention, preserving exactly who was notified."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(IssueComment, on_delete=models.CASCADE, related_name="mentions")
    membership = models.ForeignKey(WorkspaceMembership, on_delete=models.CASCADE, related_name="comment_mentions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["comment", "membership"], name="unique_comment_mention"),
        ]

    def clean(self) -> None:
        if self.membership_id and self.membership.workspace_id != self.comment.issue.project.workspace_id:
            raise ValidationError("Mentioned user must belong to the issue workspace.")


class Notification(models.Model):
    """A user inbox notification; delivery channels will consume this record later."""

    class Type(models.TextChoices):
        MENTION = "mention", "Mention"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(WorkspaceMembership, on_delete=models.CASCADE, related_name="notifications")
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="notifications")
    comment = models.ForeignKey(IssueComment, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=Type.choices)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at", "created_at"], name="notice_recipient_read_idx")]

    def clean(self) -> None:
        if self.recipient_id and self.recipient.workspace_id != self.issue.project.workspace_id:
            raise ValidationError("Notification recipient must belong to the issue workspace.")


class IssueActivity(models.Model):
    """Append-only audit entry for notable issue changes and collaboration."""

    class Event(models.TextChoices):
        CREATED = "created", "Created"
        STATUS_CHANGED = "status_changed", "Status changed"
        COMMENTED = "commented", "Commented"
        ATTACHMENT_ADDED = "attachment_added", "Attachment added"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(WorkspaceMembership, on_delete=models.PROTECT, related_name="issue_activity")
    event_type = models.CharField(max_length=24, choices=Event.choices)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["issue", "created_at"], name="activity_issue_created_idx")]


class IssueAttachment(models.Model):
    """Attachment metadata; files remain pending until a scanner marks them clean."""

    class ScanStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CLEAN = "clean", "Clean"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(WorkspaceMembership, on_delete=models.PROTECT, related_name="uploaded_attachments")
    file = models.FileField(upload_to="issue-attachments/%Y/%m/%d/")
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    scan_status = models.CharField(max_length=12, choices=ScanStatus.choices, default=ScanStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["issue", "created_at"], name="attach_issue_created_idx")]

    def clean(self) -> None:
        if self.uploaded_by_id and self.uploaded_by.workspace_id != self.issue.project.workspace_id:
            raise ValidationError("Attachment uploader must belong to the issue workspace.")


class CustomField(models.Model):
    """A project-local field definition with a JSON configuration schema."""

    class Type(models.TextChoices):
        TEXT = "text", "Text"
        SELECT = "select", "Dropdown"
        DATE = "date", "Date"
        USER = "user", "User picker"
        MULTI_SELECT = "multi_select", "Multi-select"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="custom_fields")
    name = models.CharField(max_length=100)
    key = models.SlugField(max_length=60)
    field_type = models.CharField(max_length=16, choices=Type.choices)
    configuration = models.JSONField(default=dict, blank=True)
    is_required = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(fields=["project", "key"], name="unique_custom_field_key_per_project"),
        ]


class IssueCustomFieldValue(models.Model):
    """One JSON value per issue/field pair, validated by the service layer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="custom_values")
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name="values")
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issue", "field"], name="unique_issue_custom_field_value"),
        ]
        indexes = [models.Index(fields=["field", "issue"], name="custom_value_field_issue_idx")]

    def clean(self) -> None:
        if self.field_id and self.field.project_id != self.issue.project_id:
            raise ValidationError("Custom field must belong to the issue project.")


class SavedIssueFilter(models.Model):
    """A user-owned, optionally shared saved issue query for one project."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="saved_filters")
    owner = models.ForeignKey(WorkspaceMembership, on_delete=models.CASCADE, related_name="saved_issue_filters")
    name = models.CharField(max_length=100)
    query = models.JSONField(default=dict, blank=True)
    jql = models.CharField(max_length=1_000, blank=True)
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["project", "owner", "name"], name="unique_saved_filter_name_per_owner"),
        ]

    def clean(self) -> None:
        if self.owner_id and self.owner.workspace_id != self.project.workspace_id:
            raise ValidationError("Filter owner must belong to the project workspace.")


class Worklog(models.Model):
    """An immutable unit of time spent on an issue, in seconds for precise aggregation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="worklogs")
    author = models.ForeignKey(WorkspaceMembership, on_delete=models.PROTECT, related_name="worklogs")
    seconds_spent = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["issue", "started_at"], name="worklog_issue_started_idx")]

    def clean(self) -> None:
        if self.author_id and self.author.workspace_id != self.issue.project.workspace_id:
            raise ValidationError("Worklog author must belong to the issue workspace.")
