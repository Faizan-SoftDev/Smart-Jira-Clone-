"""Read-only project workspace context endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.api.v1.auth import get_current_user
from app.infrastructure.database.models import ProjectModel, UserModel
from app.infrastructure.database.session import get_db_session

router = APIRouter(prefix="/projects", tags=["projects"])
DatabaseSession = Annotated[Session, Depends(get_db_session)]
AuthorizedUser = Annotated[UserModel, Depends(get_current_user)]


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    name: str
    description: str


@router.get("", response_model=list[ProjectResponse])
def list_projects(session: DatabaseSession, _: AuthorizedUser) -> list[ProjectModel]:
    """Return available project contexts for task creation and board filtering."""
    return list(session.scalars(select(ProjectModel).order_by(ProjectModel.key)))
