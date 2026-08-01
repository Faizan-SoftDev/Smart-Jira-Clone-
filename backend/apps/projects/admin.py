"""Admin interfaces for workspace-scoped project configuration."""

from django.contrib import admin

from .models import Project, ProjectMembership, ProjectSettings, Team, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "created_at")
    search_fields = ("name", "workspace__name")
    inlines = [TeamMembershipInline]


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "workspace", "methodology", "is_archived")
    list_filter = ("methodology", "is_archived")
    search_fields = ("key", "name", "workspace__name")
    inlines = [ProjectMembershipInline]


admin.site.register(ProjectSettings)
