"""SQLAlchemy implementation of the task repository port."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.models.task import Task, TaskStatus
from app.domain.repositories.task_repository import TaskRepository
from app.infrastructure.database.models import TaskModel


class SQLAlchemyTaskRepository(TaskRepository):
    """Transaction-safe task repository backed by SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: Task) -> Task:
        self._session.add(TaskModel.from_domain(task))
        self._commit()
        return task

    def get(self, task_id: UUID) -> Task | None:
        model = self._session.get(TaskModel, task_id)
        return model.to_domain() if model else None

    def list(self, *, limit: int, offset: int, task_type: str | None, status: TaskStatus | None, project_id: UUID | None) -> tuple[list[Task], int]:
        filters = [TaskModel.task_type == task_type] if task_type else []
        if status:
            filters.append(TaskModel.status == status)
        if project_id:
            filters.append(TaskModel.project_id == project_id)
        query = select(TaskModel).where(*filters).order_by(TaskModel.created_at.desc(), TaskModel.id).offset(offset).limit(limit)
        count = select(func.count()).select_from(TaskModel).where(*filters)
        return [model.to_domain() for model in self._session.scalars(query)], self._session.scalar(count) or 0

    def save(self, task: Task) -> Task:
        model = self._session.get(TaskModel, task.task_id)
        if model is None:
            raise LookupError(str(task.task_id))
        model.status = task.status
        model.updated_at = task.updated_at
        self._commit()
        return task

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise
