"""Read-only reporting queries for project dashboards."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.issues.models import Issue

from .models import Project


def project_summary(*, project: Project, days: int = 30) -> dict:
    """Return bounded aggregate data without loading individual issues into memory."""
    days = max(1, min(days, 365))
    since = timezone.now() - timedelta(days=days)
    issues = Issue.objects.filter(project=project)
    status_counts = list(
        issues.values("status__id", "status__name", "status__category").annotate(count=Count("id")).order_by("status__name")
    )
    priority_counts = list(issues.values("priority").annotate(count=Count("id")).order_by("priority"))
    created = issues.filter(created_at__gte=since).annotate(day=TruncDate("created_at")).values("day").annotate(created=Count("id"))
    resolved = issues.filter(status__category="done", updated_at__gte=since).annotate(day=TruncDate("updated_at")).values("day").annotate(resolved=Count("id"))
    trend: dict[str, dict] = {}
    for row in created:
        trend.setdefault(row["day"].isoformat(), {"date": row["day"].isoformat(), "created": 0, "resolved": 0})["created"] = row["created"]
    for row in resolved:
        trend.setdefault(row["day"].isoformat(), {"date": row["day"].isoformat(), "created": 0, "resolved": 0})["resolved"] = row["resolved"]
    return {
        "totals": {
            "all": issues.count(),
            "open": issues.exclude(status__category="done").count(),
            "done": issues.filter(status__category="done").count(),
        },
        "by_status": status_counts,
        "by_priority": priority_counts,
        "created_vs_resolved": [trend[key] for key in sorted(trend)],
    }
