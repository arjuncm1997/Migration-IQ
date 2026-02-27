"""Alembic migration adapter – parser for Alembic revision files."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from migrationiq.adapters.base import BaseMigrationAdapter, MigrationInfo

__all__ = ["AlembicAdapter"]

logger = logging.getLogger(__name__)

_REVISION_RE = re.compile(r"""^revision\s*[:=]\s*['"]([^'"]+)['"]""", re.MULTILINE)
_DOWN_REV_RE = re.compile(r"""^down_revision\s*[:=]\s*['"]([^'"]+)['"]""", re.MULTILINE)
_DOWN_REV_TUPLE_RE = re.compile(r"""^down_revision\s*[:=]\s*\(([^)]*)\)""", re.MULTILINE)
_DOWN_REV_NONE_RE = re.compile(r"""^down_revision\s*[:=]\s*None""", re.MULTILINE)

_OP_SQL_MAP: dict[str, str] = {
    "create_table": "CREATE TABLE",
    "drop_table": "DROP TABLE",
    "add_column": "ALTER TABLE ADD COLUMN",
    "drop_column": "ALTER TABLE DROP COLUMN",
    "alter_column": "ALTER TABLE ALTER COLUMN",
    "create_index": "CREATE INDEX",
    "drop_index": "DROP INDEX",
    "rename_table": "ALTER TABLE RENAME",
    "execute": "RAW SQL",
}


class AlembicAdapter(BaseMigrationAdapter):
    """Adapter that discovers and parses Alembic revision files."""

    def detect_framework(self) -> bool:
        indicators = [
            self.root_dir / "alembic.ini",
            self.root_dir / "alembic",
            self.root_dir / "migrations" / "env.py",
        ]
        return any(p.exists() for p in indicators)

    def discover_migrations(self) -> list[MigrationInfo]:
        migrations: list[MigrationInfo] = []
        versions_dirs = self._find_versions_dirs()
        for versions_dir in versions_dirs:
            for py_file in sorted(versions_dir.glob("*.py")):
                if py_file.name.startswith("__"):
                    continue
                try:
                    info = self._parse_revision_file(py_file)
                    if info is not None:
                        migrations.append(info)
                except Exception:
                    logger.warning("Failed to parse revision: %s", py_file, exc_info=True)
        return migrations

    def _find_versions_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        for candidate in ("alembic/versions", "migrations/versions", "versions"):
            d = self.root_dir / candidate
            if d.is_dir():
                dirs.append(d)
        if not dirs:
            for env_py in self.root_dir.rglob("env.py"):
                versions = env_py.parent / "versions"
                if versions.is_dir():
                    dirs.append(versions)
        return dirs

    def _parse_revision_file(self, path: Path) -> MigrationInfo | None:
        source = path.read_text(encoding="utf-8", errors="replace")
        revision = self._extract_revision(source)
        if revision is None:
            return None
        dependencies = self._extract_down_revision(source)
        operations = self._extract_operations(source, path)
        return MigrationInfo(
            migration_id=revision, app_label="alembic",
            dependencies=dependencies, operations=operations,
            sql_content=source, file_path=path,
        )

    @staticmethod
    def _extract_revision(source: str) -> str | None:
        match = _REVISION_RE.search(source)
        return match.group(1) if match else None

    @staticmethod
    def _extract_down_revision(source: str) -> list[str]:
        if _DOWN_REV_NONE_RE.search(source):
            return []
        match = _DOWN_REV_RE.search(source)
        if match:
            return [match.group(1)]
        match = _DOWN_REV_TUPLE_RE.search(source)
        if match:
            inner = match.group(1)
            return [s.strip().strip("'\"") for s in inner.split(",") if s.strip()]
        return []

    @staticmethod
    def _extract_operations(source: str, path: Path) -> list[str]:
        ops: list[str] = []
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return ops
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_name = _get_op_call_name(child)
                        if call_name:
                            sql_equiv = _OP_SQL_MAP.get(call_name, call_name)
                            detail = _get_first_str_arg(child)
                            label = f"{sql_equiv}: {detail}" if detail else sql_equiv
                            ops.append(label)
        return ops


def _get_op_call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        value = node.func.value
        if isinstance(value, ast.Name) and value.id == "op":
            return node.func.attr
    return None

def _get_first_str_arg(node: ast.Call) -> str:
    if node.args:
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return ""
