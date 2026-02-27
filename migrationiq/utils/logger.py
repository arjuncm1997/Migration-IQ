"""Rich-based structured logging and terminal output for MigrationIQ."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

__all__ = [
    "console",
    "print_success",
    "print_warning",
    "print_error",
    "print_info",
    "create_table",
    "create_panel",
]

_THEME = Theme(
    {
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "info": "bold cyan",
        "muted": "dim",
        "accent": "bold magenta",
    }
)

console = Console(theme=_THEME)


def print_success(message: str) -> None:
    """Print a success message with a checkmark."""
    console.print(f"[success]✔[/success] {message}")


def print_warning(message: str) -> None:
    """Print a warning message with a caution sign."""
    console.print(f"[warning]⚠[/warning] {message}")


def print_error(message: str) -> None:
    """Print an error message with a cross."""
    console.print(f"[error]✖[/error] {message}")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[info]ℹ[/info] {message}")


def create_table(
    title: str,
    columns: list[tuple[str, str]],
    rows: list[list[str]],
) -> Table:
    """Create a Rich table with the given columns and rows."""
    table = Table(title=title, show_lines=True, expand=True)
    for header, style in columns:
        table.add_column(header, style=style)
    for row in rows:
        table.add_row(*row)
    return table


def create_panel(
    content: str,
    title: str,
    style: str = "cyan",
    subtitle: str | None = None,
) -> Panel:
    """Create a Rich panel for structured output."""
    return Panel(
        Text(content),
        title=title,
        subtitle=subtitle,
        border_style=style,
        expand=True,
        padding=(1, 2),
    )
