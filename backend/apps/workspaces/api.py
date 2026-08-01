"""Workspace REST endpoints with membership-scoped querysets."""

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Workspace
from .models import WorkspaceDeletionRequest, WorkspaceMembership
from .gdpr import export_workspace_data
from .services import create_workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    """Public workspace representation; memberships stay private."""

    class Meta:
        model = Workspace
        fields = ("id", "name", "slug", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class WorkspaceListCreateView(APIView):
    """List only the current user's tenants or create a new tenant."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        workspaces = Workspace.objects.filter(memberships__user=request.user).distinct()
        return Response(WorkspaceSerializer(workspaces, many=True).data)

    def post(self, request):
        serializer = WorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = create_workspace(owner=request.user, **serializer.validated_data)
        return Response(WorkspaceSerializer(workspace).data, status=201)


class WorkspaceExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        try:
            workspace = Workspace.objects.get(pk=workspace_id, memberships__user=request.user, memberships__role=WorkspaceMembership.Role.OWNER)
        except Workspace.DoesNotExist as exc:
            raise PermissionDenied("Only a workspace owner can export data.") from exc
        return Response(export_workspace_data(workspace=workspace))


class WorkspaceDeletionRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        try:
            workspace = Workspace.objects.get(pk=workspace_id, memberships__user=request.user, memberships__role=WorkspaceMembership.Role.OWNER)
        except Workspace.DoesNotExist as exc:
            raise PermissionDenied("Only a workspace owner can request deletion.") from exc
        deletion, created = WorkspaceDeletionRequest.objects.get_or_create(workspace=workspace, defaults={"requested_by": request.user})
        return Response({"request_id": deletion.pk, "created": created}, status=201 if created else 200)
