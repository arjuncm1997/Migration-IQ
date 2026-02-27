"""Base rule interface and violation model for the MigrationIQ lint engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from migrationiq.adapters.base import MigrationInfo

__all__ = ["ViolationSeverity", "RuleViolation", "BaseRule"]


class ViolationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    severity: ViolationSeverity
    file_path: str
    message: str
    explanation: str
    suggested_fix: str
    example_snippet: str = ""
    line_hint: int | None = None


class BaseRule(ABC):
    rule_id: str = "base"
    description: str = ""

    @abstractmethod
    def evaluate(self, migration: MigrationInfo) -> list[RuleViolation]:
        """Analyse a migration and return any violations found."""
