"""Abstract base adapter for migration framework integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


__all__ = ["MigrationInfo", "BaseMigrationAdapter"]


@dataclass(frozen=True)
class MigrationInfo:
    """Normalized representation of a single migration file."""

    migration_id: str
    app_label: str
    dependencies: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    sql_content: str = ""
    file_path: Path | None = None


class BaseMigrationAdapter(ABC):
    """Interface that each migration framework adapter must implement."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()

    @abstractmethod
    def discover_migrations(self) -> list[MigrationInfo]:
        """Scan the project for migration files and return parsed info."""

    @abstractmethod
    def detect_framework(self) -> bool:
        """Return ``True`` if this adapter's framework is present in the project."""
