"""Rule: Detect risky column type changes in migrations."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING
from migrationiq.rules.base_rule import BaseRule, RuleViolation, ViolationSeverity
if TYPE_CHECKING:
    from migrationiq.adapters.base import MigrationInfo

__all__ = ["TypeChangeRule"]

_ALTER_TYPE_SQL_RE = re.compile(r"\bALTER\s+COLUMN\s+\w+\s+(SET\s+DATA\s+)?TYPE\b", re.IGNORECASE)
_DJANGO_ALTER_FIELD_RE = re.compile(r"\bAlterField\b", re.IGNORECASE)
_ALEMBIC_ALTER_COL_RE = re.compile(r"\bop\.alter_column\b", re.IGNORECASE)
_ALEMBIC_TYPE_PARAM_RE = re.compile(r"\btype_\s*=", re.IGNORECASE)


class TypeChangeRule(BaseRule):
    rule_id = "type-change"
    description = "Detects column type changes that can lose data or lock tables."

    def evaluate(self, migration: MigrationInfo) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        content = migration.sql_content
        for match in _ALTER_TYPE_SQL_RE.finditer(content):
            violations.append(self._make_violation(migration, content[:match.start()].count("\n") + 1, "ALTER COLUMN TYPE statement found"))
        for match in _DJANGO_ALTER_FIELD_RE.finditer(content):
            violations.append(self._make_violation(migration, content[:match.start()].count("\n") + 1, "Django AlterField operation found – may involve type change"))
        for match in _ALEMBIC_ALTER_COL_RE.finditer(content):
            start = match.start()
            context = content[start:min(start + 300, len(content))]
            if _ALEMBIC_TYPE_PARAM_RE.search(context):
                violations.append(self._make_violation(migration, content[:start].count("\n") + 1, "Alembic op.alter_column() with type_ parameter"))
        return violations

    @staticmethod
    def _make_violation(migration: MigrationInfo, line_no: int, message: str) -> RuleViolation:
        return RuleViolation(
            rule_id="type-change", severity=ViolationSeverity.WARNING,
            file_path=str(migration.file_path or ""), message=message,
            explanation="Changing a column's type can silently truncate or corrupt data. On large tables the ALTER may acquire an exclusive lock and cause downtime.",
            suggested_fix="1. Add a new column with the desired type.\n2. Back-fill data with a safe cast.\n3. Update application code to use the new column.\n4. Drop the old column in a subsequent release.",
            example_snippet="# Instead of:\n#   ALTER TABLE orders ALTER COLUMN amount TYPE INTEGER;\n# Use:\nALTER TABLE orders ADD COLUMN amount_new INTEGER;\nUPDATE orders SET amount_new = amount::INTEGER;\nALTER TABLE orders DROP COLUMN amount;\nALTER TABLE orders RENAME COLUMN amount_new TO amount;",
            line_hint=line_no,
        )
