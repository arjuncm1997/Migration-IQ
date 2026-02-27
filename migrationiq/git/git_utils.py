"""Safe subprocess wrappers for Git operations."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

__all__ = ["GitClient", "GitError"]

logger = logging.getLogger(__name__)


class GitError(Exception):
    def __init__(self, command: str, stderr: str, returncode: int) -> None:
        self.command = command
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(f"git {command} failed (rc={returncode}): {stderr.strip()}")


class GitClient:
    def __init__(self, repo_dir: Path | None = None) -> None:
        self.repo_dir = (repo_dir or Path.cwd()).resolve()

    def _run(self, *args: str, check: bool = True) -> str:
        cmd = ["git", *args]
        logger.debug("Running: %s (cwd=%s)", " ".join(cmd), self.repo_dir)
        try:
            result = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            raise GitError(args[0] if args else "git", "Git is not installed or not in PATH", 127)
        except subprocess.TimeoutExpired:
            raise GitError(args[0] if args else "git", "Command timed out after 30s", 124)
        if check and result.returncode != 0:
            raise GitError(args[0] if args else "git", result.stderr, result.returncode)
        return result.stdout.strip()

    def is_git_repo(self) -> bool:
        try:
            self._run("rev-parse", "--is-inside-work-tree")
            return True
        except GitError:
            return False

    def fetch(self, remote: str = "origin") -> None:
        self._run("fetch", remote)

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def rev_parse(self, ref: str) -> str:
        return self._run("rev-parse", ref)

    def merge_base(self, ref_a: str, ref_b: str) -> str:
        try:
            return self._run("merge-base", ref_a, ref_b)
        except GitError:
            return ""

    def diff_files(self, ref_a: str, ref_b: str) -> list[str]:
        output = self._run("diff", "--name-only", ref_a, ref_b, check=False)
        if not output:
            return []
        return [line.strip() for line in output.splitlines() if line.strip()]

    def commits_between(self, base_ref: str, head_ref: str) -> int:
        output = self._run("rev-list", "--count", f"{base_ref}..{head_ref}", check=False)
        try:
            return int(output)
        except ValueError:
            return 0

    def diff_stat(self, ref_a: str, ref_b: str) -> str:
        return self._run("diff", "--stat", ref_a, ref_b, check=False)
