"""In-memory Directed Acyclic Graph for migration dependency analysis."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field


__all__ = ["MigrationGraph", "GraphIssue"]


@dataclass(frozen=True)
class GraphIssue:
    """A single problem detected in the migration graph."""
    issue_type: str
    severity: str
    description: str
    nodes: list[str] = field(default_factory=list)


class MigrationGraph:
    """Directed acyclic graph representing migration dependencies."""

    def __init__(self) -> None:
        self._forward: dict[str, set[str]] = defaultdict(set)
        self._reverse: dict[str, set[str]] = defaultdict(set)
        self._nodes: set[str] = set()

    def add_node(self, node: str) -> None:
        self._nodes.add(node)

    def add_edge(self, node: str, dependency: str) -> None:
        self._nodes.add(node)
        self._nodes.add(dependency)
        self._forward[node].add(dependency)
        self._reverse[dependency].add(node)

    @property
    def nodes(self) -> frozenset[str]:
        return frozenset(self._nodes)

    def find_heads(self) -> list[str]:
        return sorted(n for n in self._nodes if not self._reverse.get(n))

    def find_roots(self) -> list[str]:
        return sorted(n for n in self._nodes if not self._forward.get(n))

    def detect_cycles(self) -> list[list[str]]:
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in self._nodes}
        parent: dict[str, str | None] = {n: None for n in self._nodes}
        cycles: list[list[str]] = []

        for start in sorted(self._nodes):
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, bool]] = [(start, False)]
            while stack:
                node, processed = stack.pop()
                if processed:
                    color[node] = BLACK
                    continue
                if color[node] == GRAY:
                    color[node] = BLACK
                    continue
                color[node] = GRAY
                stack.append((node, True))
                for dep in sorted(self._forward.get(node, set())):
                    if color[dep] == GRAY:
                        cycle = [dep, node]
                        cur = parent.get(node)
                        while cur is not None and cur != dep:
                            cycle.append(cur)
                            cur = parent.get(cur)
                        cycle.reverse()
                        cycles.append(cycle)
                    elif color[dep] == WHITE:
                        parent[dep] = node
                        stack.append((dep, False))
        return cycles

    def find_orphans(self) -> list[str]:
        return sorted(
            n for n in self._nodes
            if not self._forward.get(n) and not self._reverse.get(n)
        )

    def detect_multiple_heads(self) -> list[str]:
        heads = self.find_heads()
        return heads if len(heads) > 1 else []

    def topological_sort(self) -> list[str]:
        in_degree = {n: len(self._forward.get(n, set())) for n in self._nodes}
        queue: deque[str] = deque(sorted(n for n in self._nodes if in_degree[n] == 0))
        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in sorted(self._reverse.get(node, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        if len(result) != len(self._nodes):
            raise ValueError("Migration graph contains cycles – topological sort is impossible.")
        return result

    def missing_dependencies(self) -> list[tuple[str, str]]:
        missing: list[tuple[str, str]] = []
        for node, deps in self._forward.items():
            for dep in sorted(deps):
                if dep not in self._nodes:
                    missing.append((node, dep))
        return missing

    def analyze(self) -> list[GraphIssue]:
        issues: list[GraphIssue] = []
        heads = self.detect_multiple_heads()
        if heads:
            issues.append(GraphIssue(
                issue_type="multiple_heads", severity="critical",
                description=f"Migration graph has {len(heads)} heads – this will cause merge conflicts. Create a merge migration to resolve.",
                nodes=heads,
            ))
        cycles = self.detect_cycles()
        for cycle in cycles:
            issues.append(GraphIssue(
                issue_type="cycle", severity="critical",
                description=f"Circular dependency detected: {' → '.join(cycle)}. This will prevent migrations from running.",
                nodes=cycle,
            ))
        for node, dep in self.missing_dependencies():
            issues.append(GraphIssue(
                issue_type="missing_dependency", severity="critical",
                description=f"Migration '{node}' depends on '{dep}' which does not exist.",
                nodes=[node, dep],
            ))
        orphans = self.find_orphans()
        if orphans:
            issues.append(GraphIssue(
                issue_type="orphan", severity="warning",
                description=f"Found {len(orphans)} orphan migration(s) with no dependencies or dependents.",
                nodes=orphans,
            ))
        return issues
