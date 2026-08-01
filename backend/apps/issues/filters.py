"""Bounded JQL-lite parsing and Django-filter query helpers."""

from __future__ import annotations

import re

import django_filters
from django.db.models import Q, QuerySet

from .models import Issue


class IssueFilter(django_filters.FilterSet):
    """Supported query-string filters for a project issue list."""

    label = django_filters.CharFilter(method="filter_label")
    q = django_filters.CharFilter(method="filter_text")

    class Meta:
        model = Issue
        fields = {
            "status": ["exact"],
            "priority": ["exact"],
            "issue_type": ["exact"],
            "assignee": ["exact"],
            "reporter": ["exact"],
        }

    def filter_label(self, queryset, name, value):
        return queryset.filter(labels__contains=[value])

    def filter_text(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value))


TERM_PATTERN = re.compile(
    r"^\s*(status|priority|type|assignee|reporter|label)\s*=\s*(?:\"([^\"]+)\"|([^\s]+))\s*$",
    re.IGNORECASE,
)


def apply_jql_lite(queryset: QuerySet[Issue], expression: str) -> QuerySet[Issue]:
    """Apply a deliberately small, allow-listed ``field = value AND ...`` language."""
    if not expression.strip():
        return queryset
    filters = Q()
    for raw_term in re.split(r"\s+AND\s+", expression, flags=re.IGNORECASE):
        match = TERM_PATTERN.match(raw_term)
        if not match:
            raise ValueError("Use JQL-lite terms like: priority = high AND type = bug")
        field = match.group(1).lower()
        value = match.group(2) or match.group(3)
        lookup = {"type": "issue_type", "label": "labels__contains"}.get(field, field)
        filters &= Q(**{lookup: [value] if field == "label" else value})
    return queryset.filter(filters)
