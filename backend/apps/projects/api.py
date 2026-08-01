"""Project and team REST endpoints, always scoped through workspace access."""

from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.models import Workspace, WorkspaceMembership
from apps.workspaces.permissions import WorkspaceAction, can_access_workspace

from .models import Project, Sprint, SprintBurndownSnapshot, Team
from .permissions import ProjectAction, can_access_project
from .reports import project_summary
from .services import assign_issue_to_sprint, complete_sprint, create_project, create_sprint, create_team, start_sprint


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ("id", "name", "description", "created_at")
        read_only_fields = ("id", "created_at")


class ProjectSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)
    lead_user_id = serializers.UUIDField(source="lead.user_id", read_only=True)

    class Meta:
        model = Project
        fields = (
            "id", "name", "key", "slug", "methodology", "team", "lead_user_id",
            "is_archived", "created_at", "updated_at",
        )
        read_only_fields = ("id", "lead_user_id", "created_at", "updated_at")


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    key = serializers.CharField(max_length=10)
    slug = serializers.CharField(max_length=100)
    methodology = serializers.ChoiceField(choices=Project.Methodology.choices, default=Project.Methodology.KANBAN)
    team_id = serializers.UUIDField(required=False)


class SprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sprint
        fields = ("id", "name", "goal", "status", "start_date", "end_date", "created_at", "completed_at")
        read_only_fields = ("id", "status", "created_at", "completed_at")


class SprintIssueAssignmentSerializer(serializers.Serializer):
    issue_id = serializers.UUIDField()


class TeamListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _workspace(self, request, workspace_id):
        try:
            return Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist as exc:
            raise NotFound("Workspace not found.") from exc

    def get(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        if not can_access_workspace(user=request.user, workspace=workspace, action=WorkspaceAction.VIEW):
            raise PermissionDenied("You do not have access to this workspace.")
        teams = workspace.teams.all()
        return Response(TeamSerializer(teams, many=True).data)

    def post(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        if not can_access_workspace(user=request.user, workspace=workspace, action=WorkspaceAction.MANAGE_WORKSPACE):
            raise PermissionDenied("Only workspace administrators can create teams.")
        serializer = TeamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(TeamSerializer(create_team(workspace=workspace, **serializer.validated_data)).data, status=201)


class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _workspace(self, workspace_id):
        try:
            return Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist as exc:
            raise NotFound("Workspace not found.") from exc

    def get(self, request, workspace_id):
        workspace = self._workspace(workspace_id)
        if not can_access_workspace(user=request.user, workspace=workspace, action=WorkspaceAction.VIEW):
            raise PermissionDenied("You do not have access to this workspace.")
        allowed = Q(
            workspace__memberships__user=request.user,
            workspace__memberships__role__in=[
                WorkspaceMembership.Role.OWNER,
                WorkspaceMembership.Role.ADMIN,
                WorkspaceMembership.Role.PROJECT_LEAD,
            ],
        ) | Q(memberships__workspace_membership__user=request.user)
        projects = (
            Project.objects.filter(workspace=workspace)
            .filter(allowed)
            .select_related("team", "lead__user")
            .distinct()
        )
        return Response(ProjectSerializer(projects, many=True).data)

    def post(self, request, workspace_id):
        workspace = self._workspace(workspace_id)
        if not can_access_workspace(user=request.user, workspace=workspace, action=WorkspaceAction.MANAGE_WORKSPACE):
            raise PermissionDenied("Only workspace administrators can create projects.")
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            lead = WorkspaceMembership.objects.get(workspace=workspace, user=request.user)
        except WorkspaceMembership.DoesNotExist as exc:  # defensive; permission check already establishes it
            raise PermissionDenied("Workspace membership is required.") from exc
        team = None
        if team_id := values.pop("team_id", None):
            try:
                team = Team.objects.get(pk=team_id, workspace=workspace)
            except Team.DoesNotExist as exc:
                raise serializers.ValidationError({"team_id": "Team not found in this workspace."}) from exc
        project = create_project(workspace=workspace, lead=lead, team=team, **values)
        return Response(ProjectSerializer(project).data, status=201)


class ProjectSprintListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _project(self, project_id):
        try:
            return Project.objects.select_related("workspace").get(pk=project_id)
        except Project.DoesNotExist as exc:
            raise NotFound("Project not found.") from exc

    def get(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this project.")
        return Response(SprintSerializer(project.sprints.all(), many=True).data)

    def post(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.MANAGE):
            raise PermissionDenied("You do not have permission to plan sprints.")
        serializer = SprintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sprint = create_sprint(project=project, **serializer.validated_data)
        return Response(SprintSerializer(sprint).data, status=201)


class SprintStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, sprint_id):
        try:
            sprint = Sprint.objects.select_related("project__workspace").get(pk=sprint_id)
        except Sprint.DoesNotExist as exc:
            raise NotFound("Sprint not found.") from exc
        if not can_access_project(user=request.user, project=sprint.project, action=ProjectAction.MANAGE):
            raise PermissionDenied("You do not have permission to start sprints.")
        return Response(SprintSerializer(start_sprint(sprint=sprint)).data)


class SprintCompleteView(SprintStartView):
    def post(self, request, sprint_id):
        try:
            sprint = Sprint.objects.select_related("project__workspace").get(pk=sprint_id)
        except Sprint.DoesNotExist as exc:
            raise NotFound("Sprint not found.") from exc
        if not can_access_project(user=request.user, project=sprint.project, action=ProjectAction.MANAGE):
            raise PermissionDenied("You do not have permission to complete sprints.")
        try:
            return Response(SprintSerializer(complete_sprint(sprint=sprint)).data)
        except ValueError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class SprintIssueAssignmentView(SprintStartView):
    def post(self, request, sprint_id):
        try:
            sprint = Sprint.objects.select_related("project__workspace").get(pk=sprint_id)
        except Sprint.DoesNotExist as exc:
            raise NotFound("Sprint not found.") from exc
        if not can_access_project(user=request.user, project=sprint.project, action=ProjectAction.MANAGE):
            raise PermissionDenied("You do not have permission to plan sprints.")
        serializer = SprintIssueAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.issues.models import Issue
        try:
            issue = Issue.objects.get(pk=serializer.validated_data["issue_id"])
            assign_issue_to_sprint(sprint=sprint, issue=issue)
        except Issue.DoesNotExist as exc:
            raise serializers.ValidationError({"issue_id": "Issue not found."}) from exc
        except ValueError as exc:
            raise serializers.ValidationError({"issue_id": str(exc)}) from exc
        return Response({"issue_id": str(issue.id), "sprint_id": str(sprint.id)})


class SprintBurndownView(SprintStartView):
    def get(self, request, sprint_id):
        try:
            sprint = Sprint.objects.select_related("project__workspace").get(pk=sprint_id)
        except Sprint.DoesNotExist as exc:
            raise NotFound("Sprint not found.") from exc
        if not can_access_project(user=request.user, project=sprint.project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this sprint.")
        return Response({"sprint_id": str(sprint.id), "points": [
            {"date": item.date, "remaining_points": item.remaining_points}
            for item in SprintBurndownSnapshot.objects.filter(sprint=sprint)
        ]})


class ProjectReportSummaryView(ProjectSprintListCreateView):
    def get(self, request, project_id):
        project = self._project(project_id)
        if not can_access_project(user=request.user, project=project, action=ProjectAction.VIEW):
            raise PermissionDenied("You do not have access to this project.")
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError as exc:
            raise serializers.ValidationError({"days": "Days must be an integer."}) from exc
        return Response(project_summary(project=project, days=days))
