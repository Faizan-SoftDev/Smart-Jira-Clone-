"""Issue API routing."""

from django.urls import path

from .api import (
    IssueActivityListView, IssueAttachmentListCreateView, IssueCommentListCreateView,
    IssueTransitionView, NotificationListView, NotificationReadView, ProjectIssueListCreateView,
    ProjectBoardView, ProjectCustomFieldListCreateView, SavedFilterListCreateView, IssueBoardMoveView, IssueWorklogListCreateView,
)

urlpatterns = [
    path("projects/<uuid:project_id>/issues/", ProjectIssueListCreateView.as_view(), name="issue-list-create"),
    path("projects/<uuid:project_id>/custom-fields/", ProjectCustomFieldListCreateView.as_view(), name="custom-field-list-create"),
    path("projects/<uuid:project_id>/filters/", SavedFilterListCreateView.as_view(), name="saved-filter-list-create"),
    path("projects/<uuid:project_id>/board/", ProjectBoardView.as_view(), name="project-board"),
    path("issues/<uuid:issue_id>/transition/", IssueTransitionView.as_view(), name="issue-transition"),
    path("issues/<uuid:issue_id>/move/", IssueBoardMoveView.as_view(), name="issue-board-move"),
    path("issues/<uuid:issue_id>/worklogs/", IssueWorklogListCreateView.as_view(), name="issue-worklog-list-create"),
    path("issues/<uuid:issue_id>/comments/", IssueCommentListCreateView.as_view(), name="issue-comment-list-create"),
    path("issues/<uuid:issue_id>/attachments/", IssueAttachmentListCreateView.as_view(), name="issue-attachment-list-create"),
    path("issues/<uuid:issue_id>/activity/", IssueActivityListView.as_view(), name="issue-activity-list"),
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/<uuid:notification_id>/read/", NotificationReadView.as_view(), name="notification-read"),
]
