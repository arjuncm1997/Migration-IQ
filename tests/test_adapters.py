"""Tests for Django and Alembic adapters."""
from __future__ import annotations
from pathlib import Path
import pytest
from migrationiq.adapters.django_adapter import DjangoAdapter
from migrationiq.adapters.alembic_adapter import AlembicAdapter
from tests.conftest import (
    DJANGO_MIGRATION_0001, DJANGO_MIGRATION_0002, DJANGO_MIGRATION_DROP,
    ALEMBIC_REVISION_001, ALEMBIC_REVISION_002, ALEMBIC_REVISION_DROP, ALEMBIC_REVISION_ALTER,
)


class TestDjangoAdapterDetection:
    def test_detects_manage_py(self, tmp_path) -> None:
        (tmp_path / "manage.py").write_text("# Django")
        assert DjangoAdapter(tmp_path).detect_framework()

    def test_detects_migrations_dir(self, tmp_path) -> None:
        mig = tmp_path / "myapp" / "migrations"
        mig.mkdir(parents=True)
        (mig / "__init__.py").write_text("")
        assert DjangoAdapter(tmp_path).detect_framework()

    def test_not_detected_in_empty_dir(self, tmp_path) -> None:
        assert not DjangoAdapter(tmp_path).detect_framework()


class TestDjangoAdapterParsing:
    def test_discover_migrations(self, tmp_django_project) -> None:
        m = DjangoAdapter(tmp_django_project).discover_migrations()
        assert len(m) == 2

    def test_dependencies_extracted(self, tmp_django_project) -> None:
        migrations = DjangoAdapter(tmp_django_project).discover_migrations()
        m2 = next(m for m in migrations if "0002" in m.migration_id)
        assert "myapp.0001_initial" in m2.dependencies

    def test_operations_extracted(self, tmp_django_project) -> None:
        migrations = DjangoAdapter(tmp_django_project).discover_migrations()
        m1 = next(m for m in migrations if "0001" in m.migration_id)
        assert any("CREATE TABLE" in op for op in m1.operations)

    def test_syntax_error_skipped(self, tmp_path) -> None:
        mig = tmp_path / "badapp" / "migrations"
        mig.mkdir(parents=True)
        (mig / "__init__.py").write_text("")
        (mig / "0001_bad.py").write_text("def bad syntax {{{{")
        assert len(DjangoAdapter(tmp_path).discover_migrations()) == 0

    def test_drop_operations_extracted(self, tmp_path) -> None:
        mig = tmp_path / "myapp" / "migrations"
        mig.mkdir(parents=True)
        (mig / "__init__.py").write_text("")
        (mig / "0003_drop.py").write_text(DJANGO_MIGRATION_DROP)
        migrations = DjangoAdapter(tmp_path).discover_migrations()
        assert any("DROP TABLE" in op for op in migrations[0].operations)


class TestAlembicAdapterDetection:
    def test_detects_alembic_ini(self, tmp_path) -> None:
        (tmp_path / "alembic.ini").write_text("[alembic]\n")
        assert AlembicAdapter(tmp_path).detect_framework()

    def test_not_detected_in_empty_dir(self, tmp_path) -> None:
        assert not AlembicAdapter(tmp_path).detect_framework()


class TestAlembicAdapterParsing:
    def test_discover_revisions(self, tmp_alembic_project) -> None:
        m = AlembicAdapter(tmp_alembic_project).discover_migrations()
        assert len(m) == 2 and "abc123" in [x.migration_id for x in m]

    def test_down_revision_extracted(self, tmp_alembic_project) -> None:
        migrations = AlembicAdapter(tmp_alembic_project).discover_migrations()
        m2 = next(m for m in migrations if m.migration_id == "def456")
        assert "abc123" in m2.dependencies

    def test_initial_has_no_deps(self, tmp_alembic_project) -> None:
        migrations = AlembicAdapter(tmp_alembic_project).discover_migrations()
        m1 = next(m for m in migrations if m.migration_id == "abc123")
        assert m1.dependencies == []

    def test_drop_table_revision(self, tmp_path) -> None:
        versions = tmp_path / "alembic" / "versions"
        versions.mkdir(parents=True)
        (tmp_path / "alembic.ini").write_text("[alembic]\n")
        (tmp_path / "alembic" / "env.py").write_text("")
        (versions / "003_drop.py").write_text(ALEMBIC_REVISION_DROP)
        migrations = AlembicAdapter(tmp_path).discover_migrations()
        assert any("DROP TABLE" in op for op in migrations[0].operations)

    def test_non_revision_file_skipped(self, tmp_path) -> None:
        versions = tmp_path / "alembic" / "versions"
        versions.mkdir(parents=True)
        (tmp_path / "alembic.ini").write_text("[alembic]\n")
        (tmp_path / "alembic" / "env.py").write_text("")
        (versions / "helper.py").write_text("x = 1\n")
        assert len(AlembicAdapter(tmp_path).discover_migrations()) == 0
