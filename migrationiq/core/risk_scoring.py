"""Risk scoring system for MigrationIQ."""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field

__all__ = ["Severity", "RiskFinding", "RiskReport", "RiskScorer"]


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_score(cls, score: int) -> Severity:
        if score <= 3:
            return cls.LOW
        if score <= 6:
            return cls.MEDIUM
        if score <= 9:
            return cls.HIGH
        return cls.CRITICAL


DEFAULT_WEIGHTS: dict[str, int] = {
    "drop_table": 10, "drop_column": 8,
    "non_null_without_default": 7, "risky_type_change": 6,
    "multiple_heads": 9, "branch_behind_target": 5, "large_table_alter": 6,
}


@dataclass(frozen=True)
class RiskFinding:
    category: str
    score: int
    description: str
    file_path: str = ""


@dataclass
class RiskReport:
    findings: list[RiskFinding] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(f.score for f in self.findings)

    @property
    def severity(self) -> Severity:
        return Severity.from_score(self.total_score)

    def add(self, category: str, description: str, file_path: str = "", *, weights: dict[str, int] | None = None) -> None:
        w = weights or DEFAULT_WEIGHTS
        score = w.get(category, 5)
        self.findings.append(RiskFinding(category=category, score=score, description=description, file_path=file_path))

    @property
    def passed(self) -> bool:
        return len(self.findings) == 0


class RiskScorer:
    def __init__(self, weights: dict[str, int] | None = None) -> None:
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self._report = RiskReport()

    @property
    def report(self) -> RiskReport:
        return self._report

    def add_finding(self, category: str, description: str, file_path: str = "") -> None:
        self._report.add(category, description, file_path, weights=self.weights)

    def exceeds_threshold(self, threshold: int) -> bool:
        return self._report.total_score > threshold

    def reset(self) -> None:
        self._report = RiskReport()
