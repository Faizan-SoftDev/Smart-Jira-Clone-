"""Issue REST endpoints using service-layer commands and project-scoped reads."""

from django.db.models import Prefetch
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.projects.permissions import ProjectAction, can_access_project
from apps.workspaces.models import WorkspaceMembership

from .filters import IssueFilter, apply_jql_lite
from .models import CustomField, Issue, IssueActivity, IssueAttachment, IssueComment, IssueCustomFieldValue, Notification, SavedIssueFilter, WorkflowStatus, Worklog
from .services import add_attachment, add_comment, create_custom_field, create_issue, create_saved_filter, log_work, move_issue_on_board, transition_issue


class IssuePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class IssueSerializer(serializers.ModelSerializer):
    key = serializers.CharField(read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)
    reporter_user_id = serializers.UUIDField(source="reporter.user_id", read_only=True)
    assignee_user_id = serializers.UUIDField(source="assignee.user_id", read_only=True, allow_null=True)
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = (
            "id", "key", "number", "issue_type", "title", "description", "status", "status_name",
            "priority", "reporter_user_id", "assignee_user_id", "parent", "labels", "story_points", "custom_fields",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "key", "number", "status", "status_name", "reporter_user_id", "created_at", "updated_at")

    def get_custom_fields(self, instance):
        return {value.field.key: value.value for value in instance.custom_values.all()}


class IssueCreateSerializer(serializers.Serializer):
    issue_type = serializers.ChoiceField(choices=Issue.Type.choices, default=Issue.Type.TASK)
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(choices=Issue.Priority.choices, default=Issue.Priority.MEDIUM)
    assignee_id = serializers.UUIDField(required=False, allow_null=True)
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    labels = serializers.ListField(child=serializers.CharField(max_length=50), required=False)
    story_points = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    custom_fields = serializers.DictField(required=False)


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = ("id", "name", "key", "field_type", "configuration", "is_required", "position")
        read_only_fields = ("id",)


class SavedFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedIssueFilter
        fields = ("id", "name", "query", "jql", "is_shared", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class IssueTransitionSerializer(serializers.Serializer):
    target_status_id = serializers.UUIDField()


class BoardMoveSerializer(serializers.Serializer):
    target_status_id = serializers.UUIDField()
    before_issue_id = serializers.UUIDField(required=False, allow_null=True)


class WorklogSerializer(serializers.ModelSerializer):
    author_user_id = serializers.UUIDField(source="author.user_id", read_only=True)
    class Meta:
        model = Worklog
        fields = ("id", "seconds_spent", "started_at", "description", "author_user_id", "created_at")
        read_only_fields = ("id", "author_user_id", "created_at")


class CommentSerializer(serializers.ModelSerializer):
    author_user_id = serializers.UUIDField(source="author.user_id", read_only=True)
    mentioned_user_ids = serializers.SerializerMethodField()

    class Meta:
        model = IssueComment
        fields = ("id", "body", "author_user_id", "mentioned_user_ids", "created_at", "updated_at")

    def get_mentioned_user_ids(self, instance):
        return [str(mention.membership.user_id) for mention in instance.mentions.all()]


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=20_000)


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_user_id = serializers.UUIDField(source="uploaded_by.user_id", read_only=True)

    class Meta:
        model = IssueAttachment
        fields = ("id", "original_name", "content_type", "size_bytes", "scan_status", "uploaded_by_user_id", "created_at")


class ActivitySerializer(serializers.ModelSerializer):
    actor_user_id = serializers.UUIDField(source="actor.user_id", read_only=True)

    class Meta:
        model = IssueActivity
        fields = ("id", "event_type", "data", "actor_user_id", "created_at")


class NotificationSerializer(serializers.ModelSerializer):
    issue_key = serializers.CharField(source="issue.key", read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "notification_type", "issue", "issue_key", "comment", "data", "created_at", "read_at")


class ProjectIssueListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = IssuePagination

    def _project(self, project_id):
        try:
            return Project.objects.select_related("workspace").get(pk=project_id)
        except Project.DoesNotExist as exc:
            raise NotFound("Project not found.") from exc

    def _membership(self, request, project):
        try:
            return WorkspaceMembership.objects.get(workspace=project.workspace, user=request.user)
        except WorkspaceMembership.DoesNotExist as exc:
            raise PermissionDenied("Workspace membership is required.") from exc

    def get(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this project.")
        issues = Issue.objects.filter(project=project).select_related(
            "project", "status", "reporter__user", "assignee__user", "parent"
        ).prefetch_related(Prefetch("custom_values", queryset=IssueCustomFieldValue.objects.select_related("field")))
        issues = IssueFilter(request.query_params, queryset=issues).qs
        try:
            issues = apply_jql_lite(issues, request.query_params.get("jql", ""))
        except ValueError as exc:
            raise serializers.ValidationError({"jql": str(exc)}) from exc
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(issues, request, view=self)
        return paginator.get_paginated_response(IssueSerializer(page, many=True).data)

    def post(self, request, project_id):
        project = self._project(project_id)
        serializer = IssueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        assignee = None
        if assignee_id := values.pop("assignee_id", None):
            try:
                assignee = WorkspaceMembership.objects.get(pk=assignee_id)
            except WorkspaceMembership.DoesNotExist as exc:
                raise serializers.ValidationError({"assignee_id": "Membership not found."}) from exc
        parent = None
        if parent_id := values.pop("parent_id", None):
            try:
                parent = Issue.objects.get(pk=parent_id)
            except Issue.DoesNotExist as exc:
                raise serializers.ValidationError({"parent_id": "Issue not found."}) from exc
        issue = create_issue(
            project=project, reporter=self._membership(request, project), assignee=assignee, parent=parent, **values
        )
        return Response(IssueSerializer(issue).data, status=201)


class ProjectCustomFieldListCreateView(ProjectIssueListCreateView):
    def get(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this project.")
        return Response(CustomFieldSerializer(project.custom_fields.all(), many=True).data)

    def post(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.MANAGE):
            raise PermissionDenied("You do not have permission to configure fields.")
        serializer = CustomFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            field = create_custom_field(project=project, **serializer.validated_data)
        except ValueError as exc:
            raise serializers.ValidationError({"configuration": str(exc)}) from exc
        return Response(CustomFieldSerializer(field).data, status=201)


class SavedFilterListCreateView(ProjectIssueListCreateView):
    def get(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this project.")
        filters = project.saved_filters.filter(owner__user=request.user) | project.saved_filters.filter(is_shared=True)
        return Response(SavedFilterSerializer(filters.distinct(), many=True).data)

    def post(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this project.")
        serializer = SavedFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            saved = create_saved_filter(project=project, owner=self._membership(request, project), **serializer.validated_data)
        except ValueError as exc:
            raise serializers.ValidationError({"name": str(exc)}) from exc
        return Response(SavedFilterSerializer(saved).data, status=201)


class ProjectBoardView(ProjectIssueListCreateView):
    """Return an ordered Kanban read model with columns and minimal issue cards."""

    def get(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this project.")
        statuses = WorkflowStatus.objects.filter(workflow__project=project, workflow__is_default=True).order_by("position")
        issues = Issue.objects.filter(project=project).select_related("project", "status", "reporter__user", "assignee__user", "parent").prefetch_related(
            Prefetch("custom_values", queryset=IssueCustomFieldValue.objects.select_related("field"))
        ).order_by("board_order", "id")
        grouped = {status.id: [] for status in statuses}
        for issue in issues:
            if issue.status_id in grouped:
                grouped[issue.status_id].append(IssueSerializer(issue).data)
        return Response({"project_id": str(project.id), "columns": [
            {"id": str(status.id), "name": status.name, "category": status.category, "issues": grouped[status.id]}
            for status in statuses
        ]})


class IssueBoardMoveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, issue_id):
        try:
            issue = Issue.objects.select_related("project__workspace", "status__workflow").get(pk=issue_id)
        except Issue.DoesNotExist as exc:
            raise NotFound("Issue not found.") from exc
        serializer = BoardMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            target = WorkflowStatus.objects.select_related("workflow").get(pk=serializer.validated_data["target_status_id"])
            actor = WorkspaceMembership.objects.get(workspace=issue.project.workspace, user=request.user)
        except WorkflowStatus.DoesNotExist as exc:
            raise serializers.ValidationError({"target_status_id": "Status not found."}) from exc
        except WorkspaceMembership.DoesNotExist as exc:
            raise PermissionDenied("Workspace membership is required.") from exc
        before = None
        if before_id := serializer.validated_data.get("before_issue_id"):
            try:
                before = Issue.objects.get(pk=before_id)
            except Issue.DoesNotExist as exc:
                raise serializers.ValidationError({"before_issue_id": "Issue not found."}) from exc
        try:
            moved = move_issue_on_board(issue=issue, actor=actor, target_status=target, before_issue=before)
        except (ValueError, PermissionError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
        moved.refresh_from_db()
        return Response(IssueSerializer(moved).data)


class IssueWorklogListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _issue(self, issue_id):
        try:
            return Issue.objects.select_related("project__workspace").get(pk=issue_id)
        except Issue.DoesNotExist as exc:
            raise NotFound("Issue not found.") from exc

    def get(self, request, issue_id):
        issue = self._issue(issue_id)
        if not can_access_project(user=request.user, project=issue.project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this issue.")
        return Response(WorklogSerializer(issue.worklogs.select_related("author__user"), many=True).data)

    def post(self, request, issue_id):
        issue = self._issue(issue_id); serializer = WorklogSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        try:
            member = WorkspaceMembership.objects.get(workspace=issue.project.workspace, user=request.user)
            worklog = log_work(issue=issue, author=member, **serializer.validated_data)
        except WorkspaceMembership.DoesNotExist as exc:
            raise PermissionDenied("Workspace membership is required.") from exc
        except (ValueError, PermissionError) as exc:
            raise serializers.ValidationError({"seconds_spent": str(exc)}) from exc
        return Response(WorklogSerializer(worklog).data, status=201)


class IssueTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, issue_id):
        try:
            issue = Issue.objects.select_related("project__workspace", "status__workflow").get(pk=issue_id)
        except Issue.DoesNotExist as exc:
            raise NotFound("Issue not found.") from exc
        serializer = IssueTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            target = WorkflowStatus.objects.get(pk=serializer.validated_data["target_status_id"])
        except WorkflowStatus.DoesNotExist as exc:
            raise serializers.ValidationError({"target_status_id": "Status not found."}) from exc
        try:
            actor = WorkspaceMembership.objects.get(workspace=issue.project.workspace, user=request.user)
        except WorkspaceMembership.DoesNotExist as exc:
            raise PermissionDenied("Workspace membership is required.") from exc
        transition_issue(issue=issue, actor=actor, target_status=target)
        issue.refresh_from_db()
        return Response(IssueSerializer(issue).data)


class IssueCommentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _issue(self, issue_id):
        try:
            return Issue.objects.select_related("project__workspace").get(pk=issue_id)
        except Issue.DoesNotExist as exc:
            raise NotFound("Issue not found.") from exc

    def get(self, request, issue_id):
        issue = self._issue(issue_id)
        if not can_access_project(user=request.user, project=issue.project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this issue.")
        comments = IssueComment.objects.filter(issue=issue).select_related("author__user").prefetch_related("mentions__membership")
        return Response(CommentSerializer(comments, many=True).data)

    def post(self, request, issue_id):
        issue = self._issue(issue_id)
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = WorkspaceMembership.objects.get(workspace=issue.project.workspace, user=request.user)
        except WorkspaceMembership.DoesNotExist as exc:
            raise PermissionDenied("Workspace membership is required.") from exc
        try:
            comment = add_comment(issue=issue, author=membership, **serializer.validated_data)
        except (ValueError, PermissionError) as exc:
            raise serializers.ValidationError({"body": str(exc)}) from exc
        return Response(CommentSerializer(comment).data, status=201)


class IssueAttachmentListCreateView(IssueCommentListCreateView):
    def get(self, request, issue_id):
        issue = self._issue(issue_id)
        if not can_access_project(user=request.user, project=issue.project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this issue.")
        attachments = IssueAttachment.objects.filter(issue=issue).select_related("uploaded_by__user")
        return Response(AttachmentSerializer(attachments, many=True).data)

    def post(self, request, issue_id):
        issue = self._issue(issue_id)
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise serializers.ValidationError({"file": "A file is required."})
        try:
            membership = WorkspaceMembership.objects.get(workspace=issue.project.workspace, user=request.user)
            attachment = add_attachment(issue=issue, uploader=membership, uploaded_file=uploaded_file)
        except (ValueError, PermissionError) as exc:
            raise serializers.ValidationError({"file": str(exc)}) from exc
        return Response(AttachmentSerializer(attachment).data, status=201)


class IssueActivityListView(IssueCommentListCreateView):
    def get(self, request, issue_id):
        issue = self._issue(issue_id)
        if not can_access_project(user=request.user, project=issue.project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this issue.")
        activity = IssueActivity.objects.filter(issue=issue).select_related("actor__user")
        return Response(ActivitySerializer(activity, many=True).data)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient__user=request.user).select_related("issue__project", "comment")
        return Response(NotificationSerializer(notifications, many=True).data)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(pk=notification_id, recipient__user=request.user)
        except Notification.DoesNotExist as exc:
            raise NotFound("Notification not found.") from exc
        from django.utils import timezone
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)
