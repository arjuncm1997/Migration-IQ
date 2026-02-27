"""MigrationIQ CLI – Typer multi-command application."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from migrationiq.config.settings import load_settings
from migrationiq.core.engine import MigrationIQEngine
from migrationiq.core.risk_scoring import Severity
from migrationiq.utils.logger import (
    console, print_error, print_info, print_success, print_warning,
)

__all__ = ["app"]

app = typer.Typer(
    name="migrationiq",
    help="Git-aware migration safety CLI for Django and Alembic projects.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _load_engine(config: Path | None, project_dir: Path | None, framework: str | None) -> MigrationIQEngine:
    root = (project_dir or Path.cwd()).resolve()
    settings = load_settings(config_path=config, search_dir=root)
    if framework:
        settings.framework = framework
    return MigrationIQEngine(settings=settings, root_dir=root)


_SEVERITY_COLOR = {"CRITICAL": "bold red", "ERROR": "red", "WARNING": "yellow", "INFO": "cyan"}


def _banner() -> None:
    console.print(Panel(
        Text("MigrationIQ", style="bold magenta", justify="center"),
        subtitle="Git-aware migration safety",
        border_style="magenta", expand=False, padding=(0, 4),
    ))
    console.print()


@app.command()
def check(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to migrationiq.yaml"),
    project_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Project root directory"),
    framework: Optional[str] = typer.Option(None, "--framework", "-f", help="Migration framework: django|alembic|auto"),
) -> None:
    """Build migration graph and detect structural issues."""
    _banner()
    engine = _load_engine(config, project_dir, framework)
    with console.status("[bold cyan]Analysing migration graph…"):
        result = engine.run_check()

    console.print(Panel(
        f"[bold]Discovered {len(result.migrations)} migration(s)[/bold]\n"
        f"Heads: {', '.join(result.heads) or 'none'}\nRoots: {', '.join(result.roots) or 'none'}",
        title="📊 Migration Graph Summary", border_style="cyan",
    ))

    if not result.graph_issues:
        print_success("Migration graph is clean – no issues detected.")
        raise typer.Exit(code=0)

    table = Table(title="⚠️  Graph Issues", show_lines=True, expand=True)
    table.add_column("Type", style="bold")
    table.add_column("Severity")
    table.add_column("Description")
    table.add_column("Nodes")
    for issue in result.graph_issues:
        sev_style = "red" if issue.severity == "critical" else "yellow"
        table.add_row(issue.issue_type, f"[{sev_style}]{issue.severity.upper()}[/{sev_style}]", issue.description, ", ".join(issue.nodes[:5]))
    console.print(table)

    if result.has_critical:
        print_error("Critical issues found in migration graph.")
    else:
        print_warning("Warnings found in migration graph.")
    raise typer.Exit(code=result.exit_code)


@app.command()
def lint(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to migrationiq.yaml"),
    project_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Project root directory"),
    framework: Optional[str] = typer.Option(None, "--framework", "-f", help="Migration framework: django|alembic|auto"),
) -> None:
    """Parse migration files and detect risky operations."""
    _banner()
    engine = _load_engine(config, project_dir, framework)
    with console.status("[bold cyan]Linting migration files…"):
        result = engine.run_lint()

    if not result.violations:
        print_success("All migrations passed lint checks – no risky operations found.")
        raise typer.Exit(code=0)

    by_file: dict[str, list] = {}
    for v in result.violations:
        by_file.setdefault(v.file_path or "<unknown>", []).append(v)

    for file_path, violations in by_file.items():
        console.print(Panel(f"[bold]{file_path}[/bold]  ({len(violations)} issue(s))", border_style="yellow", expand=True))
        for v in violations:
            style = _SEVERITY_COLOR.get(v.severity.value, "white")
            console.print(f"  [{style}]● {v.severity.value}[/{style}]  {v.message}")
            if v.line_hint:
                console.print(f"    [dim]Line ~{v.line_hint}[/dim]")
            console.print(f"    [dim]Why risky:[/dim] {v.explanation}")
            console.print(f"    [dim]Suggested fix:[/dim] {v.suggested_fix}")
            if v.example_snippet:
                console.print(f"    [dim]Example:[/dim]")
                console.print(Panel(v.example_snippet, border_style="dim", expand=False))
            console.print()

    total = len(result.violations)
    crits = sum(1 for v in result.violations if v.severity.value == "CRITICAL")
    errs = sum(1 for v in result.violations if v.severity.value == "ERROR")
    warns = sum(1 for v in result.violations if v.severity.value == "WARNING")
    console.print(Panel(
        f"[bold]Total: {total}[/bold]  [red]Critical: {crits}[/red]  [red]Error: {errs}[/red]  [yellow]Warning: {warns}[/yellow]",
        title="📋 Lint Summary", border_style="cyan",
    ))
    raise typer.Exit(code=result.exit_code)


@app.command()
def compare(
    target: str = typer.Option("origin/main", "--target", "-t", help="Target branch to compare against"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to migrationiq.yaml"),
    project_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Project root directory"),
    framework: Optional[str] = typer.Option(None, "--framework", "-f", help="Migration framework"),
) -> None:
    """Compare migration graph between current branch and target."""
    _banner()
    engine = _load_engine(config, project_dir, framework)
    with console.status(f"[bold cyan]Comparing with {target}…"):
        try:
            result = engine.run_compare(target_branch=target)
        except Exception as exc:
            print_error(f"Comparison failed: {exc}")
            raise typer.Exit(code=2)

    console.print(Panel(
        f"[bold]Current:[/bold] {result.current_branch}\n[bold]Target:[/bold]  {result.target_branch}\n"
        f"[bold]Behind:[/bold]  {'Yes' if result.is_behind else 'No'}"
        + (f" ({result.commits_behind} commits)" if result.is_behind else ""),
        title="🔀 Branch Comparison", border_style="cyan",
    ))

    if result.current_only:
        table = Table(title="📝 Migrations only on YOUR branch", show_lines=True)
        table.add_column("File", style="green")
        for f in result.current_only:
            table.add_row(f)
        console.print(table)

    if result.target_only:
        table = Table(title="📥 Migrations only on TARGET branch", show_lines=True)
        table.add_column("File", style="yellow")
        for f in result.target_only:
            table.add_row(f)
        console.print(table)

    if result.parallel_migrations:
        table = Table(title="⚡ Parallel migrations (conflict risk!)", show_lines=True)
        table.add_column("File", style="red")
        for f in result.parallel_migrations:
            table.add_row(f)
        console.print(table)

    if result.suggestions:
        console.print(Panel("\n".join(f"• {s}" for s in result.suggestions), title="💡 Suggestions", border_style="green"))

    if not result.has_issues:
        print_success("No migration divergence detected.")
        raise typer.Exit(code=0)
    else:
        print_warning("Migration divergence detected – review suggestions above.")
        raise typer.Exit(code=1)


@app.command()
def ready(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to migrationiq.yaml"),
    project_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Project root directory"),
    framework: Optional[str] = typer.Option(None, "--framework", "-f", help="Migration framework"),
) -> None:
    """Run full pre-PR readiness check (compare + check + lint)."""
    _banner()
    engine = _load_engine(config, project_dir, framework)
    with console.status("[bold cyan]Running full readiness check…"):
        result = engine.run_ready()
    _print_ready_report(result.check, result.lint, result.compare, result.risk)
    raise typer.Exit(code=result.exit_code)


@app.command()
def protect(
    ci: bool = typer.Option(False, "--ci", help="CI mode – fail if risk threshold exceeded"),
    threshold: Optional[int] = typer.Option(None, "--threshold", "-T", help="Override risk threshold"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to migrationiq.yaml"),
    project_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Project root directory"),
    framework: Optional[str] = typer.Option(None, "--framework", "-f", help="Migration framework"),
) -> None:
    """Run readiness check and enforce risk threshold (for CI)."""
    _banner()
    engine = _load_engine(config, project_dir, framework)
    with console.status("[bold cyan]Running protection check…"):
        result = engine.run_protect(threshold=threshold)
    _print_ready_report(result.check, result.lint, result.compare, result.risk)

    sev = result.risk.severity
    sev_color = {Severity.LOW: "green", Severity.MEDIUM: "yellow", Severity.HIGH: "red", Severity.CRITICAL: "bold red"}.get(sev, "white")
    console.print(Panel(
        f"[bold]Risk Score:[/bold] {result.risk.total_score}  [{sev_color}]{sev.value}[/{sev_color}]\n"
        f"[bold]Threshold:[/bold] {result.threshold}\n"
        f"[bold]Status:[/bold]    {'[red]EXCEEDED[/red]' if result.exceeds_threshold else '[green]PASSED[/green]'}",
        title="🛡️  Protection Gate", border_style="magenta",
    ))

    if result.exceeds_threshold:
        print_error(f"Risk score {result.risk.total_score} exceeds threshold {result.threshold}. Merge blocked.")
        raise typer.Exit(code=2)
    print_success("Risk score within threshold. Safe to merge.")
    raise typer.Exit(code=result.exit_code)


def _print_ready_report(check, lint, compare, risk) -> None:
    console.rule("[bold cyan]Migration Graph Check")
    console.print(f"  Migrations discovered: {len(check.migrations)}")
    console.print(f"  Graph issues: {len(check.graph_issues)}")
    for issue in check.graph_issues:
        sev_style = "red" if issue.severity == "critical" else "yellow"
        console.print(f"    [{sev_style}]● {issue.severity.upper()}[/{sev_style}] {issue.description}")
    console.print()

    console.rule("[bold cyan]Migration Lint")
    console.print(f"  Violations: {len(lint.violations)}")
    for v in lint.violations:
        style = _SEVERITY_COLOR.get(v.severity.value, "white")
        console.print(f"    [{style}]● {v.severity.value}[/{style}] {v.message}")
    console.print()

    if compare:
        console.rule("[bold cyan]Branch Comparison")
        console.print(f"  Current: {compare.current_branch}")
        console.print(f"  Target:  {compare.target_branch}")
        console.print(f"  Behind:  {'Yes' if compare.is_behind else 'No'}")
        if compare.parallel_migrations:
            console.print(f"  [red]Parallel migrations: {len(compare.parallel_migrations)}[/red]")
        for s in compare.suggestions:
            console.print(f"    💡 {s}")
        console.print()

    if risk.findings:
        console.rule("[bold cyan]Risk Breakdown")
        table = Table(show_lines=True, expand=True)
        table.add_column("Category", style="bold")
        table.add_column("Score", justify="center")
        table.add_column("Description")
        table.add_column("File")
        for f in risk.findings:
            table.add_row(f.category, str(f.score), f.description, f.file_path)
        console.print(table)
        console.print()


if __name__ == "__main__":
    app()
