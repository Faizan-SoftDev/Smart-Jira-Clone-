"""Issue commands with workflow and tenant validation at the write boundary."""

from __future__ import annotations

import re
from pathlib import Path
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from apps.projects.models import Project, ProjectMembership, ProjectSettings
from apps.workspaces.models import WorkspaceMembership

from .events import broadcast_project_event
from .models import (
    CommentMention, CustomField, Issue, IssueActivity, IssueAttachment, IssueComment, IssueCustomFieldValue,
    Notification, Workflow, WorkflowStatus, WorkflowTransition,
    SavedIssueFilter, Worklog,
)


MENTION_PATTERN = re.compile(r"@([A-Za-z0-9][A-Za-z0-9._+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".txt", ".md", ".csv", ".docx", ".xlsx"}
ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/gif", "text/plain", "text/markdown",
    "text/csv", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def create_default_workflow(*, project: Project) -> Workflow:
    """Return the project's default workflow, creating a safe starter workflow once."""
    existing = Workflow.objects.filter(project=project, is_default=True).first()
    if existing:
        return existing

    workflow = Workflow.objects.create(project=project, name="Default workflow", is_default=True)
    todo = WorkflowStatus.objects.create(
        workflow=workflow, name="To Do", category=WorkflowStatus.Category.TODO, position=100
    )
    in_progress = WorkflowStatus.objects.create(
        workflow=workflow,
        name="In Progress",
        category=WorkflowStatus.Category.IN_PROGRESS,
        position=200,
    )
    done = WorkflowStatus.objects.create(
        workflow=workflow, name="Done", category=WorkflowStatus.Category.DONE, position=300
    )
    for source, target, name in (
        (todo, in_progress, "Start progress"),
        (in_progress, todo, "Move back to To Do"),
        (in_progress, done, "Complete"),
        (done, todo, "Reopen"),
    ):
        WorkflowTransition.objects.create(
            workflow=workflow, from_status=source, to_status=target, name=name
        )
    return workflow


def can_write_issues(*, membership: WorkspaceMembership, project: Project) -> bool:
    """Determine whether a membership may create or transition project issues."""
    if membership.workspace_id != project.workspace_id:
        return False
    if membership.role in {
        WorkspaceMembership.Role.OWNER,
        WorkspaceMembership.Role.ADMIN,
        WorkspaceMembership.Role.PROJECT_LEAD,
        WorkspaceMembership.Role.DEVELOPER,
    }:
        return True
    return ProjectMembership.objects.filter(
        project=project,
        workspace_membership=membership,
        role__in=[ProjectMembership.Role.LEAD, ProjectMembership.Role.CONTRIBUTOR],
    ).exists()


def create_issue(
    *,
    project: Project,
    reporter: WorkspaceMembership,
    title: str,
    issue_type: str = Issue.Type.TASK,
    description: str = "",
    priority: str = Issue.Priority.MEDIUM,
    assignee: WorkspaceMembership | None = None,
    parent: Issue | None = None,
    labels: list[str] | None = None,
    story_points: int | None = None,
    custom_fields: dict[str, object] | None = None,
) -> Issue:
    """Create an issue with an atomic, per-project sequence number.

    Locking the project's settings row serializes concurrent issue creation,
    avoiding duplicate keys without fragile application-side counting.
    """
    if not can_write_issues(membership=reporter, project=project):
        raise PermissionError("Reporter does not have permission to create issues in this project.")
    if assignee and assignee.workspace_id != project.workspace_id:
        raise ValueError("Assignee must belong to the project's workspace.")
    if parent and parent.project_id != project.id:
        raise ValueError("Parent issue must belong to the same project.")
    if issue_type == Issue.Type.SUBTASK and not parent:
        raise ValueError("A sub-task requires a parent issue.")

    with transaction.atomic():
        locked_project = Project.objects.select_for_update().get(pk=project.pk)
        settings = ProjectSettings.objects.select_for_update().get(project=locked_project)
        workflow = create_default_workflow(project=locked_project)
        initial_status = workflow.statuses.order_by("position").first()
        if not initial_status:  # defensive guard for malformed custom workflows
            raise ValueError("Default workflow must have at least one status.")
        settings.issue_counter += 1
        settings.save(update_fields=["issue_counter"])
        issue = Issue.objects.create(
            project=locked_project,
            number=settings.issue_counter,
            issue_type=issue_type,
            title=title.strip(),
            description=description,
            status=initial_status,
            priority=priority,
            reporter=reporter,
            assignee=assignee,
            parent=parent,
            labels=labels or [],
            story_points=story_points,
            board_order=settings.issue_counter * 1000,
        )
        IssueActivity.objects.create(
            issue=issue, actor=reporter, event_type=IssueActivity.Event.CREATED, data={"key": issue.key}
        )
        broadcast_project_event(
            project_id=locked_project.id,
            issue_id=issue.id,
            event_type="issue.created",
            data={"key": issue.key, "status_id": str(issue.status_id)},
        )
        if custom_fields:
            set_custom_field_values(issue=issue, values=custom_fields)
        return issue


def transition_issue(*, issue: Issue, actor: WorkspaceMembership, target_status: WorkflowStatus) -> Issue:
    """Move an issue only through a configured transition in its own workflow."""
    if not can_write_issues(membership=actor, project=issue.project):
        raise PermissionError("Actor does not have permission to transition this issue.")
    if target_status.workflow.project_id != issue.project_id:
        raise ValueError("Target status belongs to another project.")
    if not WorkflowTransition.objects.filter(
        workflow=issue.status.workflow, from_status=issue.status, to_status=target_status
    ).exists():
        raise ValueError("This workflow transition is not permitted.")

    previous_status = issue.status
    issue.status = target_status
    issue.save(update_fields=["status", "updated_at"])
    IssueActivity.objects.create(
        issue=issue,
        actor=actor,
        event_type=IssueActivity.Event.STATUS_CHANGED,
        data={"from": previous_status.name, "to": target_status.name},
    )
    broadcast_project_event(
        project_id=issue.project_id,
        issue_id=issue.id,
        event_type="issue.status_changed",
        data={"from_status_id": str(previous_status.id), "status_id": str(target_status.id)},
    )
    return issue


def move_issue_on_board(*, issue: Issue, actor: WorkspaceMembership, target_status: WorkflowStatus, before_issue: Issue | None = None) -> Issue:
    """Move an issue to a permitted status and deterministically re-rank its column.

    Re-numbering one column is O(n), a deliberate tradeoff for clear ordering
    and concurrency safety in an MVP. A future fractional-ranking strategy can
    reduce very large-column moves to O(1).
    """
    if target_status.workflow.project_id != issue.project_id:
        raise ValueError("Target status belongs to another project.")
    if before_issue and (before_issue.project_id != issue.project_id or before_issue.status_id != target_status.id):
        raise ValueError("The reference issue must be in the target column of this project.")
    if issue.status_id != target_status.id:
        transition_issue(issue=issue, actor=actor, target_status=target_status)
    elif not can_write_issues(membership=actor, project=issue.project):
        raise PermissionError("Actor does not have permission to move this issue.")

    with transaction.atomic():
        column = list(
            Issue.objects.select_for_update().filter(project=issue.project, status=target_status)
            .exclude(pk=issue.pk).order_by("board_order", "id")
        )
        insert_at = next((index for index, candidate in enumerate(column) if before_issue and candidate.pk == before_issue.pk), len(column))
        column.insert(insert_at, issue)
        for index, candidate in enumerate(column, start=1):
            order = index * 1000
            if candidate.board_order != order:
                Issue.objects.filter(pk=candidate.pk).update(board_order=order)
        issue.board_order = (insert_at + 1) * 1000
    broadcast_project_event(
        project_id=issue.project_id,
        issue_id=issue.id,
        event_type="issue.board_moved",
        data={"status_id": str(target_status.id), "board_order": issue.board_order},
    )
    return issue


def add_comment(*, issue: Issue, author: WorkspaceMembership, body: str) -> IssueComment:
    """Add a Markdown comment, resolve same-workspace email mentions, and notify them."""
    if not body.strip():
        raise ValueError("Comment body cannot be empty.")
    if not can_write_issues(membership=author, project=issue.project):
        raise PermissionError("Author does not have permission to comment on this issue.")

    with transaction.atomic():
        comment = IssueComment.objects.create(issue=issue, author=author, body=body.strip())
        emails = {match.group(1).lower() for match in MENTION_PATTERN.finditer(comment.body)}
        recipients = WorkspaceMembership.objects.select_related("user").filter(
            workspace=issue.project.workspace, user__email__in=emails
        ).exclude(pk=author.pk)
        for recipient in recipients:
            CommentMention.objects.create(comment=comment, membership=recipient)
            notification = Notification.objects.create(
                recipient=recipient,
                issue=issue,
                comment=comment,
                notification_type=Notification.Type.MENTION,
                data={"comment_id": str(comment.id), "issue_key": issue.key},
            )
            from .tasks import send_mention_email
            transaction.on_commit(lambda notification_id=notification.id: send_mention_email.delay(str(notification_id)))
        IssueActivity.objects.create(
            issue=issue, actor=author, event_type=IssueActivity.Event.COMMENTED,
            data={"comment_id": str(comment.id), "mention_count": len(recipients)},
        )
        broadcast_project_event(
            project_id=issue.project_id,
            issue_id=issue.id,
            event_type="comment.created",
            data={"comment_id": str(comment.id), "mention_count": len(recipients)},
        )
    return comment


def add_attachment(*, issue: Issue, uploader: WorkspaceMembership, uploaded_file) -> IssueAttachment:
    """Validate metadata then store a pending attachment for asynchronous malware scanning."""
    if not can_write_issues(membership=uploader, project=issue.project):
        raise PermissionError("Uploader does not have permission to add attachments.")
    suffix = Path(uploaded_file.name).suffix.lower()
    content_type = getattr(uploaded_file, "content_type", "application/octet-stream")
    if suffix not in ALLOWED_ATTACHMENT_EXTENSIONS or content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise ValueError("This file type is not allowed.")
    if uploaded_file.size > settings.MAX_ATTACHMENT_SIZE_BYTES:
        raise ValueError("Attachment exceeds the configured size limit.")
    with transaction.atomic():
        attachment = IssueAttachment.objects.create(
            issue=issue,
            uploaded_by=uploader,
            file=uploaded_file,
            original_name=uploaded_file.name[:255],
            content_type=content_type,
            size_bytes=uploaded_file.size,
        )
        IssueActivity.objects.create(
            issue=issue, actor=uploader, event_type=IssueActivity.Event.ATTACHMENT_ADDED,
            data={"attachment_id": str(attachment.id), "filename": attachment.original_name},
        )
        broadcast_project_event(
            project_id=issue.project_id,
            issue_id=issue.id,
            event_type="attachment.created",
            data={"attachment_id": str(attachment.id), "scan_status": attachment.scan_status},
        )
        from .tasks import scan_attachment
        transaction.on_commit(lambda: scan_attachment.delay(str(attachment.id)))
    return attachment


def _validate_custom_value(*, field: CustomField, value: object) -> None:
    """Validate JSON values against the field's small, explicit configuration schema."""
    choices = field.configuration.get("choices", [])
    if field.field_type == CustomField.Type.TEXT and not isinstance(value, str):
        raise ValueError(f"{field.name} must be text.")
    if field.field_type == CustomField.Type.DATE:
        if not isinstance(value, str):
            raise ValueError(f"{field.name} must be an ISO date.")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field.name} must be an ISO date.") from exc
    if field.field_type == CustomField.Type.SELECT and value not in choices:
        raise ValueError(f"{field.name} must be one of its configured choices.")
    if field.field_type == CustomField.Type.MULTI_SELECT:
        if not isinstance(value, list) or any(item not in choices for item in value):
            raise ValueError(f"{field.name} contains an invalid choice.")
    if field.field_type == CustomField.Type.USER:
        if not isinstance(value, str) or not WorkspaceMembership.objects.filter(
            workspace=field.project.workspace, user_id=value
        ).exists():
            raise ValueError(f"{field.name} must reference a workspace user.")


def set_custom_field_values(*, issue: Issue, values: dict[str, object]) -> None:
    """Upsert project field values by stable field key and reject unknown fields."""
    fields = {field.key: field for field in CustomField.objects.filter(project=issue.project)}
    unknown = set(values) - set(fields)
    if unknown:
        raise ValueError(f"Unknown custom field: {sorted(unknown)[0]}")
    for key, value in values.items():
        field = fields[key]
        _validate_custom_value(field=field, value=value)
        IssueCustomFieldValue.objects.update_or_create(issue=issue, field=field, defaults={"value": value})


def create_custom_field(*, project: Project, name: str, key: str, field_type: str, configuration: dict | None = None, is_required: bool = False, position: int = 100) -> CustomField:
    """Create a normalized project-local custom field definition."""
    normalized_key = slugify(key)
    if not normalized_key:
        raise ValueError("Custom field key must contain letters or numbers.")
    configuration = configuration or {}
    if field_type in {CustomField.Type.SELECT, CustomField.Type.MULTI_SELECT}:
        choices = configuration.get("choices")
        if not isinstance(choices, list) or not choices or not all(isinstance(choice, str) for choice in choices):
            raise ValueError("Select fields require a non-empty string choices list.")
    return CustomField.objects.create(
        project=project, name=name.strip(), key=normalized_key, field_type=field_type,
        configuration=configuration, is_required=is_required, position=position,
    )


def create_saved_filter(*, project: Project, owner: WorkspaceMembership, name: str, query: dict | None = None, jql: str = "", is_shared: bool = False) -> SavedIssueFilter:
    """Store a bounded filter definition owned by a member of the project workspace."""
    if owner.workspace_id != project.workspace_id:
        raise ValueError("Filter owner must belong to the project workspace.")
    return SavedIssueFilter.objects.create(
        project=project, owner=owner, name=name.strip(), query=query or {}, jql=jql.strip(), is_shared=is_shared
    )


def log_work(*, issue: Issue, author: WorkspaceMembership, seconds_spent: int, started_at, description: str = "") -> Worklog:
    """Persist valid issue time only for a member who can write project work."""
    if seconds_spent < 60:
        raise ValueError("Worklog time must be at least one minute.")
    if not can_write_issues(membership=author, project=issue.project):
        raise PermissionError("Author does not have permission to log work.")
    return Worklog.objects.create(issue=issue, author=author, seconds_spent=seconds_spent, started_at=started_at, description=description.strip())
