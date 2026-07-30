"""Idempotently seed local Smart Jira users and project templates.

Run inside the backend container with ``python seed_data.py`` after the
database is available. Passwords may be supplied through the seed-specific
environment variables; defaults are deliberately for local development only.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.domain.models.user import UserRole
from app.infrastructure.database.models import Base, ProjectModel, UserModel
from app.infrastructure.database.session import SessionLocal, engine
from app.infrastructure.security import hash_password

USERS = (
    ("admin@smartjira.local", "Platform Admin", UserRole.ADMIN, "SEED_ADMIN_PASSWORD"),
    ("manager@smartjira.local", "Project Manager", UserRole.PROJECT_MANAGER, "SEED_MANAGER_PASSWORD"),
    ("developer@smartjira.local", "Developer", UserRole.DEVELOPER, "SEED_DEVELOPER_PASSWORD"),
)
PROJECTS = (("CORE", "Core Platform", "Core platform delivery template"), ("AIP", "AI Pipeline", "AI planning and analytics template"))


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as session:
        users: dict[str, UserModel] = {}
        for email, name, role, password_variable in USERS:
            user = session.scalar(select(UserModel).where(UserModel.email == email))
            if user is None:
                password = os.getenv(password_variable, "ChangeMe-Local-Only-2026!")
                user = UserModel(email=email, display_name=name, role=role, password_hash=hash_password(password))
                session.add(user)
            users[email] = user
        session.flush()
        owner = users["manager@smartjira.local"]
        for key, name, description in PROJECTS:
            if session.scalar(select(ProjectModel).where(ProjectModel.key == key)) is None:
                session.add(ProjectModel(key=key, name=name, description=description, owner_id=owner.id))


async def main() -> None:
    await asyncio.to_thread(seed)


if __name__ == "__main__":
    asyncio.run(main())
