"""Rule: Detect adding a NOT NULL column without a default value."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING
from migrationiq.rules.base_rule import BaseRule, RuleViolation, ViolationSeverity
if TYPE_CHECKING:
    from migrationiq.adapters.base import MigrationInfo

__all__ = ["NonNullRule"]

_ADD_COL_NOT_NULL_SQL_RE = re.compile(r"\bADD\s+COLUMN\s+\w+\s+\w+[^;]*\bNOT\s+NULL\b(?![^;]*\bDEFAULT\b)", re.IGNORECASE | re.DOTALL)
_DJANGO_ADD_FIELD_RE = re.compile(r"\bAddField\b", re.IGNORECASE)
_DJANGO_NULL_FALSE_RE = re.compile(r"\bnull\s*=\s*False\b", re.IGNORECASE)
_DJANGO_DEFAULT_RE = re.compile(r"\bdefault\s*=", re.IGNORECASE)
_ALEMBIC_ADD_COL_RE = re.compile(r"\bop\.add_column\b", re.IGNORECASE)
_ALEMBIC_NULLABLE_FALSE_RE = re.compile(r"\bnullable\s*=\s*False\b", re.IGNORECASE)


class NonNullRule(BaseRule):
    rule_id = "non-null-without-default"
    description = "Detects ADD COLUMN NOT NULL without DEFAULT – risky for populated tables."

    def evaluate(self, migration: MigrationInfo) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        content = migration.sql_content
        for match in _ADD_COL_NOT_NULL_SQL_RE.finditer(content):
            line_no = content[:match.start()].count("\n") + 1
            violations.append(self._make_violation(migration, line_no, "SQL ADD COLUMN NOT NULL without DEFAULT detected"))
        self._check_django_add_field(content, migration, violations)
        self._check_alembic_add_column(content, migration, violations)
        return violations

    def _check_django_add_field(self, content: str, migration: MigrationInfo, violations: list[RuleViolation]) -> None:
        for match in _DJANGO_ADD_FIELD_RE.finditer(content):
            start = match.start()
            context = content[start:min(start + 300, len(content))]
            if _DJANGO_NULL_FALSE_RE.search(context) and not _DJANGO_DEFAULT_RE.search(context):
                violations.append(self._make_violation(migration, content[:start].count("\n") + 1, "Django AddField with null=False and no default value"))

    def _check_alembic_add_column(self, content: str, migration: MigrationInfo, violations: list[RuleViolation]) -> None:
        for match in _ALEMBIC_ADD_COL_RE.finditer(content):
            start = match.start()
            context = content[start:min(start + 300, len(content))]
            if _ALEMBIC_NULLABLE_FALSE_RE.search(context):
                violations.append(self._make_violation(migration, content[:start].count("\n") + 1, "Alembic op.add_column() with nullable=False"))

    def _make_violation(self, migration: MigrationInfo, line_no: int, message: str) -> RuleViolation:
        return RuleViolation(
            rule_id=self.rule_id, severity=ViolationSeverity.ERROR,
            file_path=str(migration.file_path or ""), message=message,
            explanation="Adding a NOT NULL column without a default value will fail on tables that already contain rows.",
            suggested_fix="Use a two-step migration approach:\n1. Add the column as nullable with a default value.\n2. Back-fill existing rows.\n3. In a separate migration, set NOT NULL.",
            example_snippet="# Step 1:\nALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'member';\n# Step 2:\nUPDATE users SET role = 'member' WHERE role IS NULL;\n# Step 3:\nALTER TABLE users ALTER COLUMN role SET NOT NULL;",
            line_hint=line_no,
        )
