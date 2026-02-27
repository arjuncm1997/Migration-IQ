"""Django migration adapter – AST-based parser for Django migration files."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from migrationiq.adapters.base import BaseMigrationAdapter, MigrationInfo

__all__ = ["DjangoAdapter"]

logger = logging.getLogger(__name__)

_OPERATION_SQL_MAP: dict[str, str] = {
    "CreateModel": "CREATE TABLE",
    "DeleteModel": "DROP TABLE",
    "RenameModel": "ALTER TABLE RENAME",
    "AddField": "ALTER TABLE ADD COLUMN",
    "RemoveField": "ALTER TABLE DROP COLUMN",
    "AlterField": "ALTER TABLE ALTER COLUMN",
    "RenameField": "ALTER TABLE RENAME COLUMN",
    "AddIndex": "CREATE INDEX",
    "RemoveIndex": "DROP INDEX",
    "AlterUniqueTogether": "ALTER TABLE UNIQUE",
    "AlterIndexTogether": "ALTER TABLE INDEX",
    "RunSQL": "RAW SQL",
    "RunPython": "RUN PYTHON",
}


class DjangoAdapter(BaseMigrationAdapter):
    """Adapter that discovers and parses Django migration files via AST."""

    def detect_framework(self) -> bool:
        indicators = [
            self.root_dir / "manage.py",
            self.root_dir / "settings.py",
        ]
        has_migrations_dir = any(self.root_dir.rglob("migrations/__init__.py"))
        return any(p.exists() for p in indicators) or has_migrations_dir

    def discover_migrations(self) -> list[MigrationInfo]:
        migrations: list[MigrationInfo] = []
        for init_file in self.root_dir.rglob("migrations/__init__.py"):
            migrations_dir = init_file.parent
            app_label = migrations_dir.parent.name
            for py_file in sorted(migrations_dir.glob("*.py")):
                if py_file.name == "__init__.py":
                    continue
                try:
                    info = self._parse_migration_file(py_file, app_label)
                    if info is not None:
                        migrations.append(info)
                except Exception:
                    logger.warning("Failed to parse migration: %s", py_file, exc_info=True)
        return migrations

    def _parse_migration_file(self, path: Path, app_label: str) -> MigrationInfo | None:
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            logger.warning("Syntax error in %s – skipping", path)
            return None
        migration_class = self._find_migration_class(tree)
        if migration_class is None:
            return None
        migration_id = f"{app_label}.{path.stem}"
        dependencies = self._extract_dependencies(migration_class)
        operations = self._extract_operations(migration_class)
        return MigrationInfo(
            migration_id=migration_id, app_label=app_label,
            dependencies=dependencies, operations=operations,
            sql_content=source, file_path=path,
        )

    @staticmethod
    def _find_migration_class(tree: ast.Module) -> ast.ClassDef | None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Migration":
                return node
        return None

    @staticmethod
    def _extract_dependencies(cls_node: ast.ClassDef) -> list[str]:
        deps: list[str] = []
        for node in cls_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "dependencies":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Tuple) and len(elt.elts) >= 2:
                                    app = _ast_str(elt.elts[0])
                                    name = _ast_str(elt.elts[1])
                                    if app and name:
                                        deps.append(f"{app}.{name}")
        return deps

    @staticmethod
    def _extract_operations(cls_node: ast.ClassDef) -> list[str]:
        ops: list[str] = []
        for node in cls_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "operations":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                op_name = _extract_call_name(elt)
                                sql_equiv = _OPERATION_SQL_MAP.get(op_name, op_name)
                                detail = _extract_operation_detail(elt, op_name)
                                label = f"{sql_equiv}: {detail}" if detail else sql_equiv
                                ops.append(label)
        return ops


def _ast_str(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None

def _extract_call_name(node: ast.expr) -> str:
    if not isinstance(node, ast.Call):
        return "Unknown"
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return "Unknown"

def _extract_operation_detail(node: ast.expr, op_name: str) -> str:
    if not isinstance(node, ast.Call):
        return ""
    for kw in node.keywords:
        if kw.arg in ("model_name", "name"):
            val = _ast_str(kw.value)
            if val:
                return val
    if node.args:
        val = _ast_str(node.args[0])
        if val:
            return val
    return ""
