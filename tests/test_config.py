"""Tests for configuration loading."""
from __future__ import annotations
from pathlib import Path
import pytest
from migrationiq.config.settings import MigrationIQSettings, RulesConfig, load_settings


class TestRulesConfig:
    def test_defaults(self) -> None:
        c = RulesConfig()
        assert not c.allow_drop_table and not c.allow_drop_column and c.require_two_step_non_null


class TestMigrationIQSettings:
    def test_defaults(self) -> None:
        s = MigrationIQSettings()
        assert s.database == "postgres" and s.target_branch == "origin/main" and s.risk_threshold == 7

    def test_custom_values(self) -> None:
        s = MigrationIQSettings(database="mysql", risk_threshold=5)
        assert s.database == "mysql" and s.risk_threshold == 5


class TestLoadSettings:
    def test_load_defaults_no_file(self, tmp_path) -> None:
        assert load_settings(search_dir=tmp_path).database == "postgres"

    def test_load_from_yaml(self, tmp_path) -> None:
        (tmp_path / "migrationiq.yaml").write_text("database: mysql\nrisk_threshold: 5\nrules:\n  allow_drop_table: true\n")
        s = load_settings(search_dir=tmp_path)
        assert s.database == "mysql" and s.risk_threshold == 5 and s.rules.allow_drop_table

    def test_explicit_path_takes_precedence(self, tmp_path) -> None:
        (tmp_path / "migrationiq.yaml").write_text("database: sqlite\n")
        explicit = tmp_path / "custom.yaml"
        explicit.write_text("database: mysql\n")
        assert load_settings(config_path=explicit, search_dir=tmp_path).database == "mysql"

    def test_empty_yaml_returns_defaults(self, tmp_path) -> None:
        (tmp_path / "migrationiq.yaml").write_text("")
        assert load_settings(search_dir=tmp_path).database == "postgres"

    def test_parent_dir_search(self, tmp_path) -> None:
        (tmp_path / "migrationiq.yaml").write_text("database: sqlite\n")
        child = tmp_path / "child" / "subdir"
        child.mkdir(parents=True)
        assert load_settings(search_dir=child).database == "sqlite"

    def test_backward_compat_migrasafe_yaml(self, tmp_path) -> None:
        (tmp_path / "migrasafe.yaml").write_text("database: mysql\n")
        assert load_settings(search_dir=tmp_path).database == "mysql"
