"""SQLAlchemy persistence model for task domain entities."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.domain.models.task import BugTask, FeatureTask, Task, TaskPriority, TaskStatus
from app.domain.models.user import UserRole


class Base(DeclarativeBase):
    """Base class for every SQLAlchemy declarative model."""


class UserModel(Base):
    """Authenticated platform user."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.DEVELOPER)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ProjectModel(Base):
    """A project containing tasks and its ownership boundary."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    owner: Mapped[UserModel] = relationship()


class TaskModel(Base):
    """Database representation of a feature or bug task."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_status_created_at", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    creator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), nullable=False, index=True)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority, name="task_priority"), nullable=False, index=True)
    story_points: Mapped[float] = mapped_column(Float, nullable=False)
    assignee_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    acceptance_criteria: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_reproducible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    project: Mapped[ProjectModel | None] = relationship()
    creator: Mapped[UserModel | None] = relationship(foreign_keys=[creator_id])

    @classmethod
    def from_domain(cls, task: Task) -> "TaskModel":
        """Translate a domain entity into its persistence representation."""
        values: dict[str, Any] = {
            "id": task.task_id,
            "project_id": task.project_id,
            "task_type": task.task_type,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "story_points": task.story_points,
            "assignee_id": task.assignee_id,
            "due_date": task.due_date,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "acceptance_criteria": None,
            "severity": None,
            "is_reproducible": None,
        }
        if isinstance(task, FeatureTask):
            values["acceptance_criteria"] = list(task.acceptance_criteria)
        elif isinstance(task, BugTask):
            values["severity"] = task.severity.value
            values["is_reproducible"] = task.is_reproducible
        return cls(**values)

    def to_domain(self) -> Task:
        """Translate this persistence record into an isolated domain entity."""
        common = {
            "task_id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "priority": self.priority,
            "story_points": self.story_points,
            "assignee_id": self.assignee_id,
            "due_date": self.due_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.task_type == "feature":
            return FeatureTask(self.title, self.description, acceptance_criteria=self.acceptance_criteria or [], **common)
        if self.task_type == "bug":
            return BugTask(
                self.title,
                self.description,
                severity=self.severity or "medium",
                is_reproducible=self.is_reproducible if self.is_reproducible is not None else True,
                **common,
            )
        raise ValueError(f"Unsupported persisted task type: {self.task_type}")
