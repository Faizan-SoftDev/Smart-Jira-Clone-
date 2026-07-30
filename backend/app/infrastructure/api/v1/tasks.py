"""Version 1 task endpoints and their request/response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.domain.models.task import BugSeverity, TaskPriority, TaskStatus
from app.domain.models.user import UserRole
from app.infrastructure.api.ws.kanban_sync import kanban_sync_manager
from app.infrastructure.api.v1.auth import require_roles
from app.infrastructure.database.models import UserModel
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.task_repository import SQLAlchemyTaskRepository
from app.use_cases.ai_agent import TaskAIAgent, TaskAnalysisError
from app.use_cases.task_service import TaskNotFoundError, TaskService


router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreateBase(BaseModel):
    """Validated fields common to all task creation requests."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=20_000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    story_points: float = Field(default=1.0, gt=0, le=1_000)
    project_id: UUID | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None


class FeatureTaskCreate(TaskCreateBase):
    """Request body for creating a feature task."""

    task_type: Literal["feature"]
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("acceptance_criteria")
    @classmethod
    def validate_acceptance_criteria(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("acceptance_criteria cannot contain empty values")
        return values


class BugTaskCreate(TaskCreateBase):
    """Request body for creating a bug task."""

    task_type: Literal["bug"]
    severity: BugSeverity = BugSeverity.MEDIUM
    is_reproducible: bool = True


TaskCreateRequest = Annotated[Union[FeatureTaskCreate, BugTaskCreate], Field(discriminator="task_type")]


class TaskResponse(BaseModel):
    """Task data returned by the HTTP API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    story_points: float
    project_id: UUID | None
    assignee_id: UUID | None
    due_date: date | None
    acceptance_criteria: list[str] | None
    severity: str | None
    is_reproducible: bool | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, task: object) -> "TaskResponse":
        from app.domain.models.task import BugTask, FeatureTask, Task

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        return cls(
            id=task.task_id,
            task_type=task.task_type,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            story_points=task.story_points,
            project_id=task.project_id,
            assignee_id=task.assignee_id,
            due_date=task.due_date,
            acceptance_criteria=list(task.acceptance_criteria) if isinstance(task, FeatureTask) else None,
            severity=task.severity.value if isinstance(task, BugTask) else None,
            is_reproducible=task.is_reproducible if isinstance(task, BugTask) else None,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskListResponse(BaseModel):
    """Paginated task collection response."""

    items: list[TaskResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class TaskStatusUpdate(BaseModel):
    """Validated task-status transition request."""

    model_config = ConfigDict(extra="forbid")

    status: TaskStatus


DatabaseSession = Annotated[Session, Depends(get_db_session)]
AuthorizedUser = Annotated[UserModel, Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER, UserRole.DEVELOPER))]


def get_task_service(session: DatabaseSession) -> TaskService:
    """Inject the application service with its SQLAlchemy adapter."""
    return TaskService(SQLAlchemyTaskRepository(session))


TaskApplicationService = Annotated[TaskService, Depends(get_task_service)]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreateRequest,
    service: TaskApplicationService,
    _: AuthorizedUser,
) -> TaskResponse:
    """Create a validated domain task and persist its database representation."""
    task = service.create_task(payload.task_type, payload.model_dump(exclude={"task_type"}))
    await kanban_sync_manager.broadcast_task_created(task_id=task.task_id, occurred_at=task.created_at)
    return TaskResponse.from_domain(task)


@router.get("", response_model=TaskListResponse)
def get_tasks(
    service: TaskApplicationService,
    _: AuthorizedUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    task_type: Annotated[Literal["feature", "bug"] | None, Query()] = None,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    project_id: UUID | None = None,
) -> TaskListResponse:
    """Fetch tasks with optional type/status filters and bounded pagination."""
    tasks, total = service.get_tasks(limit=limit, offset=offset, task_type=task_type, status=status_filter, project_id=project_id)
    return TaskListResponse(items=[TaskResponse.from_domain(task) for task in tasks], total=total, limit=limit, offset=offset)


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: UUID,
    payload: TaskStatusUpdate,
    service: TaskApplicationService,
    _: AuthorizedUser,
) -> TaskResponse:
    """Update a task status and publish the transition to Kanban clients."""
    try:
        task, previous_status = service.change_status(task_id, payload.status)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if previous_status is not None:
        await kanban_sync_manager.broadcast_task_status_change(
            task_id=task.task_id,
            previous_status=previous_status,
            status=task.status,
            occurred_at=task.updated_at,
        )
    return TaskResponse.from_domain(task)


@router.post("/{task_id}/analyze-ai")
async def analyze_task_with_ai(
    task_id: UUID,
    service: TaskApplicationService,
    _: Annotated[UserModel, Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER))],
) -> dict[str, object]:
    """Analyze a persisted task; developers are intentionally excluded by RBAC."""
    try:
        task = service.get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    try:
        return await TaskAIAgent().analyze_task(task.description or task.title, task.title)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except TaskAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI analysis failed") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI analysis is unavailable") from exc
