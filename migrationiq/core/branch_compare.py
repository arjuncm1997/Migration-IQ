"""Git-based branch comparison for migration divergence detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from migrationiq.git.git_utils import GitClient

__all__ = ["ComparisonReport", "BranchComparator"]


@dataclass(frozen=True)
class BranchDelta:
    file_path: str
    status: str
    branch: str


@dataclass
class ComparisonReport:
    current_branch: str = ""
    target_branch: str = ""
    is_behind: bool = False
    commits_behind: int = 0
    current_only: list[str] = field(default_factory=list)
    target_only: list[str] = field(default_factory=list)
    parallel_migrations: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.is_behind or self.parallel_migrations or self.target_only)


class BranchComparator:
    MIGRATION_PATTERNS: list[str] = ["*/migrations/*.py", "*/versions/*.py", "alembic/versions/*.py"]

    def __init__(self, git_client: GitClient | None = None, repo_dir: Path | None = None) -> None:
        self.git = git_client or GitClient(repo_dir=repo_dir)

    def compare(self, target_branch: str) -> ComparisonReport:
        report = ComparisonReport(target_branch=target_branch)
        self.git.fetch()
        report.current_branch = self.git.current_branch()
        merge_base = self.git.merge_base(report.current_branch, target_branch)
        if not merge_base:
            report.suggestions.append("Could not determine merge base. Ensure both branches share a common ancestor.")
            return report
        behind = self.git.commits_between(merge_base, target_branch)
        report.commits_behind = behind
        report.is_behind = behind > 0
        current_files = self._migration_files_in_diff(merge_base, report.current_branch)
        target_files = self._migration_files_in_diff(merge_base, target_branch)
        report.current_only = sorted(current_files - target_files)
        report.target_only = sorted(target_files - current_files)
        report.parallel_migrations = sorted(current_files & target_files)
        self._generate_suggestions(report)
        return report

    def _migration_files_in_diff(self, base_ref: str, head_ref: str) -> set[str]:
        all_files = self.git.diff_files(base_ref, head_ref)
        return {f for f in all_files if self._is_migration_file(f)}

    @staticmethod
    def _is_migration_file(path: str) -> bool:
        parts = path.replace("\\", "/").split("/")
        if not path.endswith(".py"):
            return False
        if "migrations" in parts:
            return True
        if "versions" in parts:
            return True
        return False

    @staticmethod
    def _generate_suggestions(report: ComparisonReport) -> None:
        if report.is_behind:
            report.suggestions.append(
                f"Your branch is {report.commits_behind} commit(s) behind '{report.target_branch}'. Rebase or merge the target branch first."
            )
        if report.target_only:
            report.suggestions.append(
                f"Target branch has {len(report.target_only)} new migration(s) not in your branch. Merge target into your branch and resolve any migration conflicts."
            )
        if report.parallel_migrations:
            report.suggestions.append(
                f"Found {len(report.parallel_migrations)} parallel migration file(s) modified in both branches. This is likely to cause merge conflicts. Coordinate with the other branch author."
            )
        if report.current_only and report.target_only:
            report.suggestions.append(
                "Both branches added new migrations. After merging, run 'makemigrations --merge' (Django) or 'alembic merge' (Alembic) to create a merge migration."
            )
