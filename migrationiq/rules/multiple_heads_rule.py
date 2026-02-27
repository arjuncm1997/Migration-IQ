"""Rule: Detect multiple heads in the migration graph."""
from __future__ import annotations
from typing import TYPE_CHECKING
from migrationiq.rules.base_rule import BaseRule, RuleViolation, ViolationSeverity
if TYPE_CHECKING:
    from migrationiq.adapters.base import MigrationInfo
    from migrationiq.core.migration_graph import MigrationGraph

__all__ = ["MultipleHeadsRule"]


class MultipleHeadsRule(BaseRule):
    rule_id = "multiple-heads"
    description = "Detects multiple leaf nodes in the migration graph, which indicates conflicting migration branches."

    def evaluate(self, migration: MigrationInfo) -> list[RuleViolation]:
        return []

    def evaluate_graph(self, graph: MigrationGraph) -> list[RuleViolation]:
        heads = graph.detect_multiple_heads()
        if not heads:
            return []
        return [RuleViolation(
            rule_id=self.rule_id, severity=ViolationSeverity.CRITICAL,
            file_path="<migration-graph>",
            message=f"Migration graph has {len(heads)} heads: {', '.join(heads)}",
            explanation="Multiple heads mean that the migration graph has diverged into parallel branches. The migration runner will not know which order to apply them.",
            suggested_fix="Create a merge migration that depends on all current heads:\n  Django:  python manage.py makemigrations --merge\n  Alembic: alembic merge heads",
            example_snippet=f"# Django merge migration:\nclass Migration(migrations.Migration):\n    dependencies = [\n        {', '.join(repr(h) for h in heads[:3])},\n    ]\n    operations = []",
        )]
