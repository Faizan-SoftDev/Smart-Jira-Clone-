"""User and authorization domain values."""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "Admin"
    PROJECT_MANAGER = "ProjectManager"
    DEVELOPER = "Developer"
