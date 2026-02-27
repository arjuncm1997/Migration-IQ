"""Tests for the risk scoring system."""
from __future__ import annotations
import pytest
from migrationiq.core.risk_scoring import DEFAULT_WEIGHTS, RiskReport, RiskScorer, Severity


class TestSeverity:
    @pytest.mark.parametrize("score, expected", [
        (0, Severity.LOW), (3, Severity.LOW), (4, Severity.MEDIUM),
        (6, Severity.MEDIUM), (7, Severity.HIGH), (9, Severity.HIGH),
        (10, Severity.CRITICAL), (100, Severity.CRITICAL),
    ])
    def test_from_score(self, score: int, expected: Severity) -> None:
        assert Severity.from_score(score) == expected


class TestRiskReport:
    def test_empty_report(self) -> None:
        r = RiskReport()
        assert r.total_score == 0 and r.severity == Severity.LOW and r.passed

    def test_add_finding(self) -> None:
        r = RiskReport()
        r.add("drop_table", "Dropped users table")
        assert r.total_score == DEFAULT_WEIGHTS["drop_table"] and not r.passed

    def test_multiple_findings_accumulate(self) -> None:
        r = RiskReport()
        r.add("drop_table", "Dropped users")
        r.add("drop_column", "Dropped column")
        assert r.total_score == DEFAULT_WEIGHTS["drop_table"] + DEFAULT_WEIGHTS["drop_column"]

    def test_severity_escalation(self) -> None:
        r = RiskReport()
        r.add("drop_table", "Big drop")
        assert r.severity == Severity.CRITICAL


class TestRiskScorer:
    def test_add_finding(self) -> None:
        s = RiskScorer()
        s.add_finding("drop_column", "Dropped legacy column")
        assert s.report.total_score == DEFAULT_WEIGHTS["drop_column"]

    def test_exceeds_threshold_false(self) -> None:
        s = RiskScorer()
        s.add_finding("branch_behind_target", "Behind by 2")
        assert s.exceeds_threshold(10) is False

    def test_exceeds_threshold_true(self) -> None:
        s = RiskScorer()
        s.add_finding("drop_table", "Dropped users")
        s.add_finding("drop_column", "Dropped column")
        assert s.exceeds_threshold(7) is True

    def test_reset(self) -> None:
        s = RiskScorer()
        s.add_finding("drop_table", "test")
        s.reset()
        assert s.report.total_score == 0 and s.report.passed

    def test_unknown_category_default_weight(self) -> None:
        s = RiskScorer()
        s.add_finding("custom_issue", "Unknown")
        assert s.report.total_score == 5
