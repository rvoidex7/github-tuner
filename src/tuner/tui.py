"""
TUI for GitHub Tuner
"""
import logging
from typing import List, Dict, Any
import datetime
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich import box
from rich.logging import RichHandler
from rich.align import Align

class TuiLogHandler(logging.Handler):
    """Custom logging handler to redirect logs to the TUI."""
    def __init__(self, dashboard):
        super().__init__()
        self.dashboard = dashboard

    def emit(self, record):
        log_entry = self.format(record)
        self.dashboard.add_log(log_entry, record.levelno)

class TunerDashboard:
    def __init__(self, console: Console):
        self.console = console
        self.layout = Layout()
        self.logs: List[Text] = []
        self.findings: List[Dict[str, Any]] = []
        self.status_message = "Initializing..."
        self.iteration_info = "Waiting to start..."
        self.stats = {"scanned": 0, "analyzed": 0, "errors": 0}

        self._setup_layout()

    def _setup_layout(self):
        """Define the TUI layout."""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        self.layout["main"].split_row(
            Layout(name="findings", ratio=2),
            Layout(name="logs", ratio=1)
        )

    def update_status(self, message: str):
        """Update the status message in the header."""
        self.status_message = message

    def update_stats(self, scanned: int = 0, analyzed: int = 0, errors: int = 0):
        """Update processing statistics."""
        self.stats["scanned"] = scanned
        self.stats["analyzed"] = analyzed
        self.stats["errors"] = errors

    def add_finding(self, finding: Dict[str, Any]):
        """Add a finding to the list."""
        self.findings.insert(0, finding)
        # Keep only top 20
        self.findings = self.findings[:20]

    def add_log(self, message: str, level: int):
        """Add a log message."""
        color = "white"
        if level >= logging.ERROR:
            color = "red"
        elif level >= logging.WARNING:
            color = "yellow"
        elif level >= logging.INFO:
            color = "blue"
        elif level == logging.DEBUG:
            color = "dim"

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        text = Text(f"[{timestamp}] {message}", style=color)
        self.logs.append(text)
        # Keep only last 50 logs
        self.logs = self.logs[-50:]

    def _generate_header(self) -> Panel:
        """Create the header panel."""
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        grid.add_row(
            f"[b]GitHub Tuner[/b] - {self.status_message}",
            f"[bold magenta]{self.iteration_info}[/bold magenta]"
        )
        return Panel(grid, style="white on blue")

    def _generate_findings_table(self) -> Panel:
        """Create the findings table."""
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Title", style="bold green")
        table.add_column("Score", style="magenta", justify="right")
        table.add_column("Summary", ratio=1)

        for f in self.findings:
            summary = f.get("summary", "") or f.get("description", "") or ""
            summary = summary.replace("\n", " ")[:60] + "..."
            score = f.get("score", 0.0)
            table.add_row(
                f.get("title", "Unknown"),
                f"{score:.2f}",
                summary
            )

        return Panel(table, title="[b]Recent & High Signal Findings[/b]", border_style="green")

    def _generate_log_panel(self) -> Panel:
        """Create the log panel."""
        log_group = Group(*self.logs)
        return Panel(log_group, title="[b]Activity Log[/b]", border_style="yellow")

    def _generate_footer(self) -> Panel:
        """Create the footer with stats."""
        stats_text = (
            f"Scanned: [bold]{self.stats['scanned']}[/bold] | "
            f"Analyzed: [bold]{self.stats['analyzed']}[/bold] | "
            f"Errors: [bold red]{self.stats['errors']}[/bold red]"
        )
        return Panel(Align.center(stats_text), style="white on black")

    def __rich__(self) -> Layout:
        """Render the layout."""
        self.layout["header"].update(self._generate_header())
        self.layout["findings"].update(self._generate_findings_table())
        self.layout["logs"].update(self._generate_log_panel())
        self.layout["footer"].update(self._generate_footer())
        return self.layout
