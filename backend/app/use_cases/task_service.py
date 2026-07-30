"""Task application service that coordinates domain entities and persistence."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.task import Task, TaskFactory, TaskStatus
from app.domain.repositories.task_repository import TaskRepository


class TaskNotFoundError(LookupError):
    """Raised when a requested task does not exist."""


class TaskService:
    """Application boundary for task workflows."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def create_task(self, task_type: str, attributes: dict[str, object]) -> Task:
        return self._repository.add(TaskFactory.create(task_type, **attributes))

    def get_tasks(
        self, *, limit: int, offset: int, task_type: str | None, status: TaskStatus | None, project_id: UUID | None = None
    ) -> tuple[list[Task], int]:
        return self._repository.list(limit=limit, offset=offset, task_type=task_type, status=status, project_id=project_id)

    def get_task(self, task_id: UUID) -> Task:
        """Return one task or raise the application-level not-found error."""
        task = self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError(str(task_id))
        return task

    def change_status(self, task_id: UUID, status: TaskStatus) -> tuple[Task, TaskStatus | None]:
        task = self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError(str(task_id))
        previous_status = task.status
        if previous_status == status:
            return task, None
        task.move_to(status)
        return self._repository.save(task), previous_status
