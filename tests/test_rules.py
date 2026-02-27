"""Tests for all lint rules."""
from __future__ import annotations
import pytest
from migrationiq.adapters.base import MigrationInfo
from migrationiq.core.migration_graph import MigrationGraph
from migrationiq.rules.drop_table_rule import DropTableRule
from migrationiq.rules.drop_column_rule import DropColumnRule
from migrationiq.rules.non_null_rule import NonNullRule
from migrationiq.rules.type_change_rule import TypeChangeRule
from migrationiq.rules.multiple_heads_rule import MultipleHeadsRule
from tests.conftest import (
    DJANGO_MIGRATION_0001, DJANGO_MIGRATION_DROP, DJANGO_MIGRATION_ALTER,
    ALEMBIC_REVISION_DROP, ALEMBIC_REVISION_002, ALEMBIC_REVISION_ALTER,
)


class TestDropTableRule:
    def test_no_violation_on_create(self, sample_migration_info) -> None:
        assert len(DropTableRule().evaluate(sample_migration_info)) == 0

    def test_django_delete_model(self, drop_migration_info) -> None:
        violations = DropTableRule().evaluate(drop_migration_info)
        assert any("DeleteModel" in v.message or "DROP TABLE" in v.message for v in violations)

    def test_alembic_drop_table(self) -> None:
        m = MigrationInfo(migration_id="abc", app_label="alembic", sql_content=ALEMBIC_REVISION_DROP)
        assert len(DropTableRule().evaluate(m)) >= 1

    def test_raw_sql_drop_table(self) -> None:
        m = MigrationInfo(migration_id="raw", app_label="test", sql_content="DROP TABLE IF EXISTS old_users;")
        assert len(DropTableRule().evaluate(m)) >= 1

    def test_violation_has_explanation(self, drop_migration_info) -> None:
        for v in DropTableRule().evaluate(drop_migration_info):
            if "DeleteModel" in v.message:
                assert v.explanation and v.suggested_fix and v.severity.value == "CRITICAL"


class TestDropColumnRule:
    def test_no_violation_on_create(self, sample_migration_info) -> None:
        assert len(DropColumnRule().evaluate(sample_migration_info)) == 0

    def test_django_remove_field(self, drop_migration_info) -> None:
        assert len(DropColumnRule().evaluate(drop_migration_info)) >= 1

    def test_alembic_drop_column(self) -> None:
        m = MigrationInfo(migration_id="abc", app_label="alembic", sql_content=ALEMBIC_REVISION_002)
        assert len(DropColumnRule().evaluate(m)) >= 1

    def test_raw_sql_drop_column(self) -> None:
        m = MigrationInfo(migration_id="raw", app_label="test", sql_content="ALTER TABLE users DROP COLUMN legacy;")
        assert len(DropColumnRule().evaluate(m)) >= 1

    def test_violation_severity_is_error(self) -> None:
        m = MigrationInfo(migration_id="raw", app_label="test", sql_content="ALTER TABLE users DROP COLUMN legacy;")
        assert all(v.severity.value == "ERROR" for v in DropColumnRule().evaluate(m))


class TestNonNullRule:
    def test_no_violation_on_safe_migration(self, sample_migration_info) -> None:
        assert len(NonNullRule().evaluate(sample_migration_info)) == 0

    def test_raw_sql_not_null_without_default(self) -> None:
        m = MigrationInfo(migration_id="raw", app_label="test", sql_content="ALTER TABLE users ADD COLUMN age INTEGER NOT NULL;")
        assert len(NonNullRule().evaluate(m)) >= 1

    def test_raw_sql_not_null_with_default_passes(self) -> None:
        m = MigrationInfo(migration_id="raw", app_label="test", sql_content="ALTER TABLE users ADD COLUMN age INTEGER NOT NULL DEFAULT 0;")
        assert len(NonNullRule().evaluate(m)) == 0

    def test_alembic_nullable_false(self) -> None:
        m = MigrationInfo(migration_id="abc", app_label="alembic", sql_content=ALEMBIC_REVISION_002)
        assert len(NonNullRule().evaluate(m)) >= 1

    def test_django_add_field_null_false(self) -> None:
        m = MigrationInfo(migration_id="myapp.0002", app_label="myapp", sql_content=(
            "class Migration(migrations.Migration):\n    operations = [\n"
            "        migrations.AddField(model_name='User', name='age', field=models.IntegerField(null=False)),\n    ]\n"
        ))
        assert len(NonNullRule().evaluate(m)) >= 1


class TestTypeChangeRule:
    def test_no_violation_on_create(self, sample_migration_info) -> None:
        assert len(TypeChangeRule().evaluate(sample_migration_info)) == 0

    def test_django_alter_field(self, alter_migration_info) -> None:
        assert len(TypeChangeRule().evaluate(alter_migration_info)) >= 1

    def test_alembic_alter_column_with_type(self) -> None:
        m = MigrationInfo(migration_id="jkl012", app_label="alembic", sql_content=ALEMBIC_REVISION_ALTER)
        assert len(TypeChangeRule().evaluate(m)) >= 1

    def test_raw_sql_alter_type(self) -> None:
        m = MigrationInfo(migration_id="raw", app_label="test", sql_content="ALTER TABLE users ALTER COLUMN age SET DATA TYPE BIGINT;")
        assert len(TypeChangeRule().evaluate(m)) >= 1

    def test_violation_is_warning_severity(self) -> None:
        m = MigrationInfo(migration_id="raw", app_label="test", sql_content="ALTER TABLE users ALTER COLUMN age TYPE BIGINT;")
        assert all(v.severity.value == "WARNING" for v in TypeChangeRule().evaluate(m))


class TestMultipleHeadsRule:
    def test_no_violation_single_head(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        assert len(MultipleHeadsRule().evaluate_graph(g)) == 0

    def test_violation_on_multiple_heads(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "a")
        violations = MultipleHeadsRule().evaluate_graph(g)
        assert len(violations) == 1 and violations[0].severity.value == "CRITICAL"

    def test_per_file_evaluate_is_noop(self, sample_migration_info) -> None:
        assert MultipleHeadsRule().evaluate(sample_migration_info) == []
