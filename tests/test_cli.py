"""Tests for CLI command registration and basic invocation."""
from __future__ import annotations
import pytest
from typer.testing import CliRunner
from migrationiq.cli.main import app

runner = CliRunner()


class TestCLIHelp:
    def test_main_help(self) -> None:
        r = runner.invoke(app, ["--help"])
        assert r.exit_code == 0

    def test_check_help(self) -> None:
        assert runner.invoke(app, ["check", "--help"]).exit_code == 0

    def test_lint_help(self) -> None:
        assert runner.invoke(app, ["lint", "--help"]).exit_code == 0

    def test_compare_help(self) -> None:
        assert runner.invoke(app, ["compare", "--help"]).exit_code == 0

    def test_ready_help(self) -> None:
        assert runner.invoke(app, ["ready", "--help"]).exit_code == 0

    def test_protect_help(self) -> None:
        assert runner.invoke(app, ["protect", "--help"]).exit_code == 0


class TestCheckCommand:
    def test_check_empty_project(self, tmp_path) -> None:
        assert runner.invoke(app, ["check", "--dir", str(tmp_path)]).exit_code == 0

    def test_check_with_django_project(self, tmp_django_project) -> None:
        assert runner.invoke(app, ["check", "--dir", str(tmp_django_project)]).exit_code == 0


class TestLintCommand:
    def test_lint_empty_project(self, tmp_path) -> None:
        assert runner.invoke(app, ["lint", "--dir", str(tmp_path)]).exit_code == 0

    def test_lint_with_django_project(self, tmp_django_project) -> None:
        assert runner.invoke(app, ["lint", "--dir", str(tmp_django_project)]).exit_code in (0, 1)
