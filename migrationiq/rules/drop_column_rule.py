"""Rule: Detect DROP COLUMN operations in migrations."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING
from migrationiq.rules.base_rule import BaseRule, RuleViolation, ViolationSeverity
if TYPE_CHECKING:
    from migrationiq.adapters.base import MigrationInfo

__all__ = ["DropColumnRule"]

_DROP_COL_SQL_RE = re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE)
_DJANGO_REMOVE_FIELD_RE = re.compile(r"\bRemoveField\b", re.IGNORECASE)
_ALEMBIC_DROP_COL_RE = re.compile(r"\bop\.drop_column\b", re.IGNORECASE)


class DropColumnRule(BaseRule):
    rule_id = "drop-column"
    description = "Detects DROP COLUMN operations that may cause data loss."

    def evaluate(self, migration: MigrationInfo) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        content = migration.sql_content
        patterns: list[tuple[re.Pattern[str], str]] = [
            (_DROP_COL_SQL_RE, "DROP COLUMN statement found"),
            (_DJANGO_REMOVE_FIELD_RE, "Django RemoveField operation found"),
            (_ALEMBIC_DROP_COL_RE, "Alembic op.drop_column() call found"),
        ]
        for pattern, msg in patterns:
            for match in pattern.finditer(content):
                line_no = content[:match.start()].count("\n") + 1
                violations.append(RuleViolation(
                    rule_id=self.rule_id, severity=ViolationSeverity.ERROR,
                    file_path=str(migration.file_path or ""), message=msg,
                    explanation="Dropping a column removes data permanently. Active application code referencing this column will break immediately.",
                    suggested_fix="1. Deploy code that no longer reads/writes the column first.\n2. Mark the column as deprecated (nullable).\n3. Drop the column in a later release.",
                    example_snippet="# Step 1 – Make column nullable (safe):\nALTER TABLE users ALTER COLUMN legacy_field DROP NOT NULL;\n\n# Step 2 – In a later migration:\nALTER TABLE users DROP COLUMN legacy_field;",
                    line_hint=line_no,
                ))
        return violations
