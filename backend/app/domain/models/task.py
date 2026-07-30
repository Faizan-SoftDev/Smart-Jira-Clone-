"""Framework-independent task domain entities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, ClassVar
from uuid import UUID, uuid4


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BugSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Task(ABC):
    """Encapsulated base entity for every work item."""

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        task_id: UUID | None = None,
        project_id: UUID | None = None,
        status: TaskStatus = TaskStatus.TODO,
        priority: TaskPriority = TaskPriority.MEDIUM,
        story_points: float = 1.0,
        assignee_id: UUID | None = None,
        due_date: date | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.__task_id = task_id or uuid4()
        self.__project_id = project_id
        self.__created_at = self._normalize_datetime(created_at or datetime.now(timezone.utc))
        self.__updated_at = self._normalize_datetime(updated_at or self.__created_at)
        self.__title = ""
        self.__description = ""
        self.__status = TaskStatus.TODO
        self.__priority = TaskPriority.MEDIUM
        self.__story_points = 1.0
        self.__assignee_id: UUID | None = None
        self.__due_date: date | None = None
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.story_points = story_points
        self.assignee_id = assignee_id
        self.due_date = due_date

    @property
    def task_id(self) -> UUID:
        return self.__task_id

    @property
    def project_id(self) -> UUID | None:
        return self.__project_id

    @property
    def created_at(self) -> datetime:
        return self.__created_at

    @property
    def updated_at(self) -> datetime:
        return self.__updated_at

    @property
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("title must be a non-empty string")
        self.__title = value.strip()

    @property
    def description(self) -> str:
        return self.__description

    @description.setter
    def description(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("description must be a string")
        self.__description = value.strip()

    @property
    def status(self) -> TaskStatus:
        return self.__status

    @status.setter
    def status(self, value: TaskStatus | str) -> None:
        self.__status = self._as_enum(value, TaskStatus, "status")

    @property
    def priority(self) -> TaskPriority:
        return self.__priority

    @priority.setter
    def priority(self, value: TaskPriority | str) -> None:
        self.__priority = self._as_enum(value, TaskPriority, "priority")

    @property
    def story_points(self) -> float:
        return self.__story_points

    @story_points.setter
    def story_points(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise TypeError("story_points must be a finite number")
        if value <= 0:
            raise ValueError("story_points must be greater than zero")
        self.__story_points = float(value)

    @property
    def assignee_id(self) -> UUID | None:
        return self.__assignee_id

    @assignee_id.setter
    def assignee_id(self, value: UUID | None) -> None:
        if value is not None and not isinstance(value, UUID):
            raise TypeError("assignee_id must be a UUID or None")
        self.__assignee_id = value

    @property
    def due_date(self) -> date | None:
        return self.__due_date

    @due_date.setter
    def due_date(self, value: date | None) -> None:
        if value is not None and (not isinstance(value, date) or isinstance(value, datetime)):
            raise TypeError("due_date must be a date or None")
        self.__due_date = value

    def move_to(self, status: TaskStatus | str) -> None:
        self.status = status
        self.__updated_at = datetime.now(timezone.utc)

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Return the stable concrete task type."""

    @abstractmethod
    def calculate_complexity_multiplier(self) -> float:
        """Return task-type-specific planning complexity."""

    @property
    def estimated_effort(self) -> float:
        return round(self.story_points * self.calculate_complexity_multiplier(), 2)

    @staticmethod
    def _as_enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
        try:
            return enum_type(value)
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(item.value for item in enum_type)
            raise ValueError(f"{field_name} must be one of: {allowed}") from exc

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError("created_at must be a datetime")
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class FeatureTask(Task):
    """A user-facing capability with acceptance criteria."""

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        acceptance_criteria: list[str] | tuple[str, ...] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(title, description, **kwargs)
        self.__acceptance_criteria: tuple[str, ...] = ()
        self.acceptance_criteria = acceptance_criteria

    @property
    def task_type(self) -> str:
        return "feature"

    @property
    def acceptance_criteria(self) -> tuple[str, ...]:
        return self.__acceptance_criteria

    @acceptance_criteria.setter
    def acceptance_criteria(self, value: list[str] | tuple[str, ...]) -> None:
        if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("acceptance_criteria must contain non-empty strings")
        self.__acceptance_criteria = tuple(item.strip() for item in value)

    def calculate_complexity_multiplier(self) -> float:
        return round(1.0 + min(len(self.acceptance_criteria), 10) * 0.1, 2)


class BugTask(Task):
    """A defect with severity and reproducibility signals."""

    _MULTIPLIERS: ClassVar[dict[BugSeverity, float]] = {
        BugSeverity.LOW: 0.8,
        BugSeverity.MEDIUM: 1.0,
        BugSeverity.HIGH: 1.4,
        BugSeverity.CRITICAL: 2.0,
    }

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        severity: BugSeverity | str = BugSeverity.MEDIUM,
        is_reproducible: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(title, description, **kwargs)
        self.__severity = BugSeverity.MEDIUM
        self.__is_reproducible = True
        self.severity = severity
        self.is_reproducible = is_reproducible

    @property
    def task_type(self) -> str:
        return "bug"

    @property
    def severity(self) -> BugSeverity:
        return self.__severity

    @severity.setter
    def severity(self, value: BugSeverity | str) -> None:
        self.__severity = self._as_enum(value, BugSeverity, "severity")

    @property
    def is_reproducible(self) -> bool:
        return self.__is_reproducible

    @is_reproducible.setter
    def is_reproducible(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("is_reproducible must be a boolean")
        self.__is_reproducible = value

    def calculate_complexity_multiplier(self) -> float:
        multiplier = self._MULTIPLIERS[self.severity]
        return round(multiplier if self.is_reproducible else multiplier + 0.25, 2)


class TaskFactory:
    """Factory for dynamic creation of concrete task entities."""

    _TASK_TYPES: ClassVar[dict[str, type[Task]]] = {"feature": FeatureTask, "bug": BugTask}

    @classmethod
    def create(cls, task_type: str, /, **attributes: Any) -> Task:
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValueError("task_type must be a non-empty string")
        normalized_type = task_type.strip().lower()
        task_class = cls._TASK_TYPES.get(normalized_type)
        if task_class is None:
            raise ValueError(f"unsupported task_type '{task_type}'")
        return task_class(**attributes)
