from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.issues.services import create_issue
from apps.projects.services import create_project
from apps.workspaces.services import create_workspace


class Command(BaseCommand):
    help = "Create a local TaskCraft admin, workspace, project, and starter issues."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(email="admin@taskcraft.local", defaults={"display_name": "TaskCraft Admin", "is_staff": True, "is_superuser": True})
        if created:
            user.set_password("ChangeMe123!"); user.save()
        workspace = user.created_workspaces.filter(slug="demo").first()
        if workspace is None:
            workspace = create_workspace(owner=user, name="Demo Workspace", slug="demo")
        membership = workspace.memberships.get(user=user)
        project, _ = workspace.projects.get_or_create(key="DEMO", defaults={"name": "Demo Project", "slug": "demo-project", "lead": membership})
        if not project.issues.exists():
            create_issue(project=project, reporter=membership, title="Welcome to TaskCraft")
            create_issue(project=project, reporter=membership, title="Move this card across the board")
        self.stdout.write(self.style.SUCCESS("Seeded admin@taskcraft.local (password: ChangeMe123!)"))
