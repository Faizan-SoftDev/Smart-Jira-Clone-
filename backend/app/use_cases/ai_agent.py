"""AI-assisted task analysis application service."""

from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field


class TaskAnalysis(BaseModel):
    """Schema returned by the task-planning AI service."""

    model_config = ConfigDict(extra="forbid")

    estimated_story_points: int = Field(ge=1, le=21)
    suggested_tags: list[str] = Field(max_length=10)
    potential_engineering_blockers: list[str] = Field(max_length=10)


class TaskAnalysisError(RuntimeError):
    """Raised when a model response cannot produce a valid task analysis."""


class TaskAIAgent:
    """Analyze work descriptions using OpenAI Structured Outputs."""

    _SYSTEM_INSTRUCTIONS = (
        "You are a staff software engineer helping plan Jira tasks. Estimate "
        "implementation effort using Fibonacci-style story points from 1 to 21. "
        "Suggest concise, lowercase, hyphenated tags that describe the relevant "
        "technical area or work type. Identify concrete engineering blockers or "
        "dependencies only; return an empty blockers list if there are none. Base "
        "all conclusions solely on the supplied task information."
    )

    def __init__(self, client: AsyncOpenAI | None = None, model: str | None = None) -> None:
        self._client = client or AsyncOpenAI()
        self._model = model or os.getenv("OPENAI_TASK_ANALYSIS_MODEL", "gpt-5.6")

    async def analyze_task(self, description: str, title: str | None = None) -> dict[str, Any]:
        """Return a JSON-serializable effort estimate, tags, and blockers."""
        if not isinstance(description, str) or not description.strip():
            raise ValueError("description must be a non-empty string")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            raise ValueError("title must be a non-empty string when provided")

        task_text = f"Title: {title.strip()}\n\nDescription:\n{description.strip()}" if title else description.strip()
        response = await self._client.responses.parse(
            model=self._model,
            input=[
                {"role": "system", "content": self._SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": task_text},
            ],
            text_format=TaskAnalysis,
        )
        analysis = response.output_parsed
        if analysis is None:
            raise TaskAnalysisError("OpenAI returned no structured task analysis")
        return analysis.model_dump(mode="json")
