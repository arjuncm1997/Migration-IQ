"""Tests for the MigrationIQ orchestration engine."""
from __future__ import annotations
from pathlib import Path
import pytest
from migrationiq.config.settings import MigrationIQSettings
from migrationiq.core.engine import MigrationIQEngine, CheckResult, LintResult
from tests.conftest import DJANGO_MIGRATION_0001, DJANGO_MIGRATION_0002, DJANGO_MIGRATION_DROP


@pytest.fixture
def django_project_with_drop(tmp_path) -> Path:
    app_dir = tmp_path / "myapp" / "migrations"
    app_dir.mkdir(parents=True)
    (app_dir / "__init__.py").write_text("")
    (app_dir / "0001_initial.py").write_text(DJANGO_MIGRATION_0001)
    (app_dir / "0002_add_email.py").write_text(DJANGO_MIGRATION_0002)
    (app_dir / "0003_drop.py").write_text(DJANGO_MIGRATION_DROP)
    (tmp_path / "manage.py").write_text("# manage.py")
    return tmp_path


class TestCheckResult:
    def test_exit_code_0_when_clean(self, tmp_django_project) -> None:
        e = MigrationIQEngine(settings=MigrationIQSettings(framework="django"), root_dir=tmp_django_project)
        assert e.run_check().exit_code == 0

    def test_migrations_discovered(self, tmp_django_project) -> None:
        assert len(MigrationIQEngine(settings=MigrationIQSettings(framework="django"), root_dir=tmp_django_project).run_check().migrations) == 2


class TestLintResult:
    def test_lint_detects_drop_table(self, django_project_with_drop) -> None:
        r = MigrationIQEngine(settings=MigrationIQSettings(framework="django"), root_dir=django_project_with_drop).run_lint()
        assert any(v.rule_id == "drop-table" for v in r.violations)

    def test_lint_detects_drop_column(self, django_project_with_drop) -> None:
        r = MigrationIQEngine(settings=MigrationIQSettings(framework="django"), root_dir=django_project_with_drop).run_lint()
        assert any(v.rule_id == "drop-column" for v in r.violations)


class TestEngineAutoDetect:
    def test_auto_detects_django(self, tmp_django_project) -> None:
        assert len(MigrationIQEngine(settings=MigrationIQSettings(framework="auto"), root_dir=tmp_django_project).run_check().migrations) == 2

    def test_auto_detects_alembic(self, tmp_alembic_project) -> None:
        assert len(MigrationIQEngine(settings=MigrationIQSettings(framework="auto"), root_dir=tmp_alembic_project).run_check().migrations) == 2

    def test_empty_dir_returns_no_migrations(self, tmp_path) -> None:
        assert len(MigrationIQEngine(settings=MigrationIQSettings(framework="auto"), root_dir=tmp_path).run_check().migrations) == 0


class TestReadyAndProtect:
    def test_ready_returns_result(self, tmp_django_project) -> None:
        assert MigrationIQEngine(settings=MigrationIQSettings(framework="django"), root_dir=tmp_django_project).run_ready().risk is not None

    def test_protect_below_threshold(self, tmp_django_project) -> None:
        r = MigrationIQEngine(settings=MigrationIQSettings(framework="django"), root_dir=tmp_django_project).run_protect(threshold=50)
        assert not r.exceeds_threshold

    def test_protect_above_threshold(self, django_project_with_drop) -> None:
        r = MigrationIQEngine(settings=MigrationIQSettings(framework="django"), root_dir=django_project_with_drop).run_protect(threshold=1)
        assert r.exceeds_threshold and r.exit_code == 2

    def test_rules_config_disables_drop_table(self, django_project_with_drop) -> None:
        s = MigrationIQSettings(framework="django", rules={"allow_drop_table": True, "allow_drop_column": True})
        r = MigrationIQEngine(settings=s, root_dir=django_project_with_drop).run_lint()
        assert not any(v.rule_id in ("drop-table", "drop-column") for v in r.violations)
