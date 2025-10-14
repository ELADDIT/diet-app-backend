"""Utility helpers for running lightweight migrations in tests or scripts."""

from importlib import import_module
from pathlib import Path
from typing import Iterable

from database import engine


def available_migrations() -> Iterable[str]:
    base_path = Path(__file__).parent
    for file in sorted(base_path.glob("[0-9][0-9][0-9]_*.py")):
        yield file.stem


def run_migrations() -> None:
    for migration in available_migrations():
        module = import_module(f"migrations.{migration}")
        if hasattr(module, "upgrade"):
            module.upgrade()


__all__ = ["available_migrations", "run_migrations", "engine"]
