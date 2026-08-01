"""Admin registration for initial workflow and issue operations."""

from django.contrib import admin

from .models import Issue, Workflow, WorkflowStatus, WorkflowTransition


class WorkflowStatusInline(admin.TabularInline):
    model = WorkflowStatus
    extra = 0


class WorkflowTransitionInline(admin.TabularInline):
    model = WorkflowTransition
    extra = 0


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "is_default")
    inlines = [WorkflowStatusInline, WorkflowTransitionInline]


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "project", "status", "priority", "assignee")
    list_filter = ("issue_type", "priority", "status")
    search_fields = ("title", "description", "project__key")
