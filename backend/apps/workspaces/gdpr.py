"""Workspace GDPR export and deletion-request use cases."""

from apps.issues.models import Issue


def export_workspace_data(*, workspace) -> dict:
    """Return portable JSON data without credentials, passwords, or refresh tokens."""
    issues = Issue.objects.filter(project__workspace=workspace).select_related("project", "status")
    return {"workspace": {"id": str(workspace.id), "name": workspace.name}, "issues": [
        {"key": issue.key, "project": issue.project.key, "title": issue.title, "status": issue.status.name,
         "priority": issue.priority, "created_at": issue.created_at.isoformat()} for issue in issues
    ]}
