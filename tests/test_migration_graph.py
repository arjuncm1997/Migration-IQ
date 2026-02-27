"""Tests for MigrationGraph – DAG operations and analysis."""
from __future__ import annotations
import pytest
from migrationiq.core.migration_graph import MigrationGraph


class TestMigrationGraphConstruction:
    def test_add_node(self) -> None:
        g = MigrationGraph()
        g.add_node("a")
        assert "a" in g.nodes

    def test_add_edge_registers_both_nodes(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        assert "a" in g.nodes and "b" in g.nodes

    def test_nodes_are_unique(self) -> None:
        g = MigrationGraph()
        g.add_node("a")
        g.add_node("a")
        assert len(g.nodes) == 1


class TestHeadsAndRoots:
    def test_single_chain_has_one_head(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "b")
        assert g.find_heads() == ["c"]

    def test_single_chain_has_one_root(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "b")
        assert g.find_roots() == ["a"]

    def test_forked_graph_has_multiple_heads(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "a")
        assert sorted(g.find_heads()) == ["b", "c"]

    def test_detect_multiple_heads_empty_for_single(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        assert g.detect_multiple_heads() == []


class TestCycleDetection:
    def test_no_cycle_in_dag(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "b")
        assert g.detect_cycles() == []

    def test_simple_cycle(self) -> None:
        g = MigrationGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        assert len(g.detect_cycles()) >= 1

    def test_three_node_cycle(self) -> None:
        g = MigrationGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        assert len(g.detect_cycles()) >= 1


class TestOrphans:
    def test_isolated_node_is_orphan(self) -> None:
        g = MigrationGraph()
        g.add_node("orphan")
        g.add_edge("b", "a")
        assert "orphan" in g.find_orphans()

    def test_connected_node_is_not_orphan(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        assert g.find_orphans() == []


class TestTopologicalSort:
    def test_linear_chain(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "b")
        order = g.topological_sort()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_diamond(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "a")
        g.add_edge("d", "b")
        g.add_edge("d", "c")
        order = g.topological_sort()
        assert order.index("a") < order.index("d")

    def test_cycle_raises(self) -> None:
        g = MigrationGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        with pytest.raises(ValueError, match="cycle"):
            g.topological_sort()


class TestAnalyze:
    def test_clean_graph(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        assert len(g.analyze()) == 0

    def test_multiple_heads_detected(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_edge("c", "a")
        assert any(i.issue_type == "multiple_heads" for i in g.analyze())

    def test_orphan_detected(self) -> None:
        g = MigrationGraph()
        g.add_edge("b", "a")
        g.add_node("lonely")
        assert any(i.issue_type == "orphan" for i in g.analyze())
