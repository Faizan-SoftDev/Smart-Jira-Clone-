#!/usr/bin/env python
"""Django's command-line utility for TaskCraft."""

import os
import sys


def main() -> None:
    """Run Django management commands using the development settings by default."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - only reached on an incomplete setup
        raise ImportError(
            "Django is not installed. Activate .venv and install backend/requirements.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
