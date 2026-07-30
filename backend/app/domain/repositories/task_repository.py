"""Task persistence port used by application use cases."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.task import Task, TaskStatus


class TaskRepository(ABC):
    """Persistence contract; implementations belong in infrastructure."""

    @abstractmethod
    def add(self, task: Task) -> Task:
        """Persist a newly created task."""

    @abstractmethod
    def get(self, task_id: UUID) -> Task | None:
        """Return a task by identity, if it exists."""

    @abstractmethod
    def list(self, *, limit: int, offset: int, task_type: str | None, status: TaskStatus | None, project_id: UUID | None) -> tuple[list[Task], int]:
        """Return a page of tasks and its total count."""

    @abstractmethod
    def save(self, task: Task) -> Task:
        """Persist changes to an existing task."""
