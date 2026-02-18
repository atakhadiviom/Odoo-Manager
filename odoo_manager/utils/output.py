"""
Output formatting utilities using Rich.
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

console = Console()


def success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗[/red] {message}")


def warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


# Alias for compatibility
warn = warning


def info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_table(headers: list[str], rows: list[list[Any]], title: str = "") -> None:
    """Print a table with the given headers and rows."""
    table = Table(title=title)
    for header in headers:
        table.add_column(header)

    for row in rows:
        table.add_row(*[str(cell) for cell in row])

    console.print(table)


def print_panel(content: str, title: str = "", style: str = "") -> None:
    """Print content in a panel."""
    console.print(Panel(content, title=title, style=style))


def print_json(data: dict[str, Any]) -> None:
    """Print data as JSON."""
    import json
    console.print_json(json.dumps(data, indent=2, default=str))


class Spinner:
    """A context manager for showing a spinner during long operations."""

    def __init__(self, message: str):
        self.message = message
        self.progress = None
        self.task_id = None

    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        )
        self.task_id = self.progress.add_task(self.message)
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, message: str):
        """Update the spinner message."""
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, description=message)
