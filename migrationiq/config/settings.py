"""Pydantic-based configuration model and YAML loader for MigrationIQ."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


__all__ = ["RulesConfig", "MigrationIQSettings", "load_settings"]

_CONFIG_FILE_NAMES: list[str] = [
    "migrationiq.yaml",
    "migrationiq.yml",
    ".migrationiq.yaml",
    ".migrationiq.yml",
    "migrasafe.yaml",
    "migrasafe.yml",
]


class RulesConfig(BaseModel):
    """Per-rule toggles and behaviour settings."""

    allow_drop_table: bool = Field(
        default=False,
        description="Allow DROP TABLE operations without raising a violation.",
    )
    allow_drop_column: bool = Field(
        default=False,
        description="Allow DROP COLUMN operations without raising a violation.",
    )
    require_two_step_non_null: bool = Field(
        default=True,
        description="Require two-step migration for adding non-null columns.",
    )


class MigrationIQSettings(BaseModel):
    """Top-level MigrationIQ configuration."""

    database: str = Field(
        default="postgres",
        description="Target database engine (postgres, mysql, sqlite).",
    )
    target_branch: str = Field(
        default="origin/main",
        description="Git ref to compare against (e.g. origin/main).",
    )
    risk_threshold: int = Field(
        default=7,
        description="Maximum acceptable cumulative risk score.",
    )
    migration_dirs: list[str] = Field(
        default_factory=lambda: ["."],
        description="Directories to scan for migration files.",
    )
    framework: str = Field(
        default="auto",
        description="Migration framework: 'django', 'alembic', or 'auto' for detection.",
    )
    rules: RulesConfig = Field(
        default_factory=RulesConfig,
        description="Per-rule configuration.",
    )


def _find_config_file(search_dir: Path) -> Path | None:
    """Walk up from *search_dir* looking for a config file."""
    current = search_dir.resolve()
    while True:
        for name in _CONFIG_FILE_NAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_settings(
    config_path: Path | None = None,
    search_dir: Path | None = None,
) -> MigrationIQSettings:
    """Load settings from a YAML file, falling back to defaults."""
    raw: dict[str, Any] = {}

    if config_path is not None:
        resolved = Path(config_path).resolve()
        if resolved.is_file():
            raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    else:
        found = _find_config_file(search_dir or Path.cwd())
        if found is not None:
            raw = yaml.safe_load(found.read_text(encoding="utf-8")) or {}

    return MigrationIQSettings(**raw)
