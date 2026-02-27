"""Rule: Detect DROP TABLE operations in migrations."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING
from migrationiq.rules.base_rule import BaseRule, RuleViolation, ViolationSeverity
if TYPE_CHECKING:
    from migrationiq.adapters.base import MigrationInfo

__all__ = ["DropTableRule"]

_DROP_TABLE_SQL_RE = re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)
_DJANGO_DELETE_MODEL_RE = re.compile(r"\bDeleteModel\b|\bRemoveModel\b", re.IGNORECASE)
_ALEMBIC_DROP_TABLE_RE = re.compile(r"\bop\.drop_table\b", re.IGNORECASE)


class DropTableRule(BaseRule):
    rule_id = "drop-table"
    description = "Detects DROP TABLE operations that cause irreversible data loss."

    def evaluate(self, migration: MigrationInfo) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        content = migration.sql_content
        patterns: list[tuple[re.Pattern[str], str]] = [
            (_DROP_TABLE_SQL_RE, "DROP TABLE statement found"),
            (_DJANGO_DELETE_MODEL_RE, "Django DeleteModel / RemoveModel operation found"),
            (_ALEMBIC_DROP_TABLE_RE, "Alembic op.drop_table() call found"),
        ]
        for pattern, msg in patterns:
            for match in pattern.finditer(content):
                line_no = content[:match.start()].count("\n") + 1
                violations.append(RuleViolation(
                    rule_id=self.rule_id, severity=ViolationSeverity.CRITICAL,
                    file_path=str(migration.file_path or ""), message=msg,
                    explanation="Dropping a table permanently removes all data. This operation is irreversible in production.",
                    suggested_fix="1. Rename the table instead of dropping it.\n2. Keep the table for a deprecation period.\n3. Back up data before dropping.\n4. Use a two-step migration.",
                    example_snippet="# Instead of:\n#   DROP TABLE users;\n# Use:\nALTER TABLE users RENAME TO users_deprecated;\n-- Drop in the next release after verifying no usage.",
                    line_hint=line_no,
                ))
        return violations
