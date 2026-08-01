"""Project API routing."""

from django.urls import path

from .api import ProjectListCreateView, ProjectReportSummaryView, ProjectSprintListCreateView, SprintBurndownView, SprintCompleteView, SprintIssueAssignmentView, SprintStartView, TeamListCreateView

urlpatterns = [
    path("workspaces/<uuid:workspace_id>/teams/", TeamListCreateView.as_view(), name="team-list-create"),
    path("workspaces/<uuid:workspace_id>/projects/", ProjectListCreateView.as_view(), name="project-list-create"),
    path("projects/<uuid:project_id>/sprints/", ProjectSprintListCreateView.as_view(), name="sprint-list-create"),
    path("projects/<uuid:project_id>/reports/summary/", ProjectReportSummaryView.as_view(), name="project-report-summary"),
    path("sprints/<uuid:sprint_id>/start/", SprintStartView.as_view(), name="sprint-start"),
    path("sprints/<uuid:sprint_id>/complete/", SprintCompleteView.as_view(), name="sprint-complete"),
    path("sprints/<uuid:sprint_id>/issues/", SprintIssueAssignmentView.as_view(), name="sprint-issue-assign"),
    path("sprints/<uuid:sprint_id>/burndown/", SprintBurndownView.as_view(), name="sprint-burndown"),
]
