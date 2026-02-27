"""Orchestration engine – ties adapters, graphs, rules, and scoring together."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from migrationiq.adapters.base import BaseMigrationAdapter, MigrationInfo
from migrationiq.adapters.django_adapter import DjangoAdapter
from migrationiq.adapters.alembic_adapter import AlembicAdapter
from migrationiq.core.migration_graph import MigrationGraph, GraphIssue
from migrationiq.core.risk_scoring import RiskScorer, RiskReport
from migrationiq.core.branch_compare import BranchComparator, ComparisonReport
from migrationiq.config.settings import MigrationIQSettings
from migrationiq.rules.base_rule import BaseRule, RuleViolation
from migrationiq.rules.drop_table_rule import DropTableRule
from migrationiq.rules.drop_column_rule import DropColumnRule
from migrationiq.rules.non_null_rule import NonNullRule
from migrationiq.rules.type_change_rule import TypeChangeRule
from migrationiq.rules.multiple_heads_rule import MultipleHeadsRule
from migrationiq.git.git_utils import GitClient

__all__ = ["MigrationIQEngine", "CheckResult", "LintResult", "ReadyResult", "ProtectResult"]


class CheckResult:
    def __init__(self, migrations: list[MigrationInfo], graph_issues: list[GraphIssue], heads: list[str], roots: list[str]) -> None:
        self.migrations = migrations
        self.graph_issues = graph_issues
        self.heads = heads
        self.roots = roots

    @property
    def has_critical(self) -> bool:
        return any(i.severity == "critical" for i in self.graph_issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.graph_issues)

    @property
    def exit_code(self) -> int:
        if self.has_critical:
            return 2
        if self.has_warnings:
            return 1
        return 0


class LintResult:
    def __init__(self, violations: list[RuleViolation]) -> None:
        self.violations = violations

    @property
    def has_critical(self) -> bool:
        return any(v.severity.value == "CRITICAL" for v in self.violations)

    @property
    def has_errors(self) -> bool:
        return any(v.severity.value == "ERROR" for v in self.violations)

    @property
    def exit_code(self) -> int:
        if self.has_critical:
            return 2
        if self.has_errors:
            return 1
        return 0


class ReadyResult:
    def __init__(self, check: CheckResult, lint: LintResult, compare: ComparisonReport | None, risk: RiskReport) -> None:
        self.check = check
        self.lint = lint
        self.compare = compare
        self.risk = risk

    @property
    def exit_code(self) -> int:
        return max(self.check.exit_code, self.lint.exit_code)


class ProtectResult(ReadyResult):
    def __init__(self, check: CheckResult, lint: LintResult, compare: ComparisonReport | None, risk: RiskReport, threshold: int) -> None:
        super().__init__(check, lint, compare, risk)
        self.threshold = threshold

    @property
    def exceeds_threshold(self) -> bool:
        return self.risk.total_score > self.threshold

    @property
    def exit_code(self) -> int:
        base = super().exit_code
        if self.exceeds_threshold:
            return max(base, 2)
        return base


class MigrationIQEngine:
    """Central orchestrator for all MigrationIQ operations."""

    def __init__(self, settings: MigrationIQSettings, root_dir: Path | None = None) -> None:
        self.settings = settings
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self._adapter: BaseMigrationAdapter | None = None
        self._rules: list[BaseRule] = self._build_rules()

    def _resolve_adapter(self) -> BaseMigrationAdapter:
        if self._adapter is not None:
            return self._adapter
        if self.settings.framework == "django":
            self._adapter = DjangoAdapter(self.root_dir)
        elif self.settings.framework == "alembic":
            self._adapter = AlembicAdapter(self.root_dir)
        else:
            django = DjangoAdapter(self.root_dir)
            alembic = AlembicAdapter(self.root_dir)
            if django.detect_framework():
                self._adapter = django
            elif alembic.detect_framework():
                self._adapter = alembic
            else:
                self._adapter = django
        return self._adapter

    def _build_rules(self) -> list[BaseRule]:
        rules: list[BaseRule] = []
        cfg = self.settings.rules
        if not cfg.allow_drop_table:
            rules.append(DropTableRule())
        if not cfg.allow_drop_column:
            rules.append(DropColumnRule())
        if cfg.require_two_step_non_null:
            rules.append(NonNullRule())
        rules.append(TypeChangeRule())
        rules.append(MultipleHeadsRule())
        return rules

    def _build_graph(self, migrations: list[MigrationInfo]) -> MigrationGraph:
        graph = MigrationGraph()
        for m in migrations:
            graph.add_node(m.migration_id)
            for dep in m.dependencies:
                graph.add_edge(m.migration_id, dep)
        return graph

    def run_check(self) -> CheckResult:
        adapter = self._resolve_adapter()
        migrations = adapter.discover_migrations()
        graph = self._build_graph(migrations)
        issues = graph.analyze()
        return CheckResult(migrations=migrations, graph_issues=issues, heads=graph.find_heads(), roots=graph.find_roots())

    def run_lint(self) -> LintResult:
        adapter = self._resolve_adapter()
        migrations = adapter.discover_migrations()
        graph = self._build_graph(migrations)
        violations: list[RuleViolation] = []
        for rule in self._rules:
            for m in migrations:
                violations.extend(rule.evaluate(m))
            if isinstance(rule, MultipleHeadsRule):
                violations.extend(rule.evaluate_graph(graph))
        return LintResult(violations=violations)

    def run_compare(self, target_branch: str | None = None) -> ComparisonReport:
        target = target_branch or self.settings.target_branch
        comparator = BranchComparator(repo_dir=self.root_dir)
        return comparator.compare(target)

    def run_ready(self) -> ReadyResult:
        compare: ComparisonReport | None = None
        try:
            compare = self.run_compare()
        except Exception:
            pass
        check = self.run_check()
        lint = self.run_lint()
        scorer = RiskScorer()
        for v in lint.violations:
            category_map = {
                "drop-table": "drop_table", "drop-column": "drop_column",
                "non-null-without-default": "non_null_without_default",
                "type-change": "risky_type_change", "multiple-heads": "multiple_heads",
            }
            scorer.add_finding(category_map.get(v.rule_id, v.rule_id), v.message, v.file_path)
        for issue in check.graph_issues:
            if issue.issue_type == "multiple_heads":
                scorer.add_finding("multiple_heads", issue.description)
        if compare and compare.is_behind:
            scorer.add_finding("branch_behind_target", f"Branch is {compare.commits_behind} commits behind target")
        return ReadyResult(check=check, lint=lint, compare=compare, risk=scorer.report)

    def run_protect(self, threshold: int | None = None) -> ProtectResult:
        ready = self.run_ready()
        thr = threshold if threshold is not None else self.settings.risk_threshold
        return ProtectResult(check=ready.check, lint=ready.lint, compare=ready.compare, risk=ready.risk, threshold=thr)
