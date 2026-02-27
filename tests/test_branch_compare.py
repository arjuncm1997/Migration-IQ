"""Tests for branch comparison logic (Git operations are mocked)."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from migrationiq.core.branch_compare import BranchComparator, ComparisonReport
from migrationiq.git.git_utils import GitClient


class TestComparisonReport:
    def test_no_issues(self) -> None:
        assert ComparisonReport(current_branch="f/x", target_branch="origin/main").has_issues is False

    def test_behind_is_issue(self) -> None:
        assert ComparisonReport(is_behind=True, commits_behind=3).has_issues is True

    def test_parallel_is_issue(self) -> None:
        assert ComparisonReport(parallel_migrations=["a.py"]).has_issues is True

    def test_target_only_is_issue(self) -> None:
        assert ComparisonReport(target_only=["b.py"]).has_issues is True


class TestBranchComparator:
    def _make_mock_git(self, branch="feature/add-users", merge_base="abc123", commits_behind=0,
                       diff_current=None, diff_target=None) -> MagicMock:
        mock = MagicMock(spec=GitClient)
        mock.fetch.return_value = None
        mock.current_branch.return_value = branch
        mock.merge_base.return_value = merge_base
        mock.commits_between.return_value = commits_behind
        def diff_files(a, b):
            if b == "origin/main":
                return diff_target or []
            return diff_current or []
        mock.diff_files.side_effect = diff_files
        return mock

    def test_clean_comparison(self) -> None:
        r = BranchComparator(git_client=self._make_mock_git()).compare("origin/main")
        assert not r.is_behind and r.parallel_migrations == [] and r.current_only == []

    def test_branch_behind(self) -> None:
        r = BranchComparator(git_client=self._make_mock_git(commits_behind=5)).compare("origin/main")
        assert r.is_behind and r.commits_behind == 5 and any("behind" in s.lower() for s in r.suggestions)

    def test_current_only_migrations(self) -> None:
        r = BranchComparator(git_client=self._make_mock_git(diff_current=["myapp/migrations/0005_new.py"])).compare("origin/main")
        assert "myapp/migrations/0005_new.py" in r.current_only

    def test_target_only_migrations(self) -> None:
        r = BranchComparator(git_client=self._make_mock_git(diff_target=["myapp/migrations/0004_other.py"])).compare("origin/main")
        assert "myapp/migrations/0004_other.py" in r.target_only

    def test_parallel_migrations(self) -> None:
        shared = ["myapp/migrations/0005_conflict.py"]
        r = BranchComparator(git_client=self._make_mock_git(diff_current=shared, diff_target=shared)).compare("origin/main")
        assert r.parallel_migrations == shared and any("parallel" in s.lower() for s in r.suggestions)

    def test_no_merge_base(self) -> None:
        r = BranchComparator(git_client=self._make_mock_git(merge_base="")).compare("origin/main")
        assert any("merge base" in s.lower() for s in r.suggestions)

    def test_non_migration_files_ignored(self) -> None:
        r = BranchComparator(git_client=self._make_mock_git(diff_current=["src/models.py", "README.md"])).compare("origin/main")
        assert r.current_only == []
