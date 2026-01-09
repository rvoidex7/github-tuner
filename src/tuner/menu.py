import sys
import os
import asyncio
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich import box
import time

from tuner.storage import TunerStorage

class InteractiveMenu:
    def __init__(self):
        self.console = Console()
        self.db_path = "data/tuner.db"
        self.agent_process = None
        self.running = True

    def main_loop(self):
        """Main TUI Loop."""
        while self.running:
            self.print_dashboard()
            choice = self.console.input("\n[bold blue]Command > [/bold blue]").strip().lower()
            
            if choice == 's':
                self.toggle_agent()
            elif choice == 'r':
                self.run_review()
            elif choice == 'l':
                self.view_logs()
            elif choice == 'q':
                self.running = False
                if self.agent_process:
                    self.agent_process.terminate()
            else:
                pass # Refresh

    def print_dashboard(self):
        self.console.clear()
        
        # 1. Status Section
        status_color = "green" if self.agent_process and self.agent_process.poll() is None else "red"
        status_text = "RUNNING" if status_color == "green" else "STOPPED"
        
        # Stats (Async fetch hack for synchronous TUI)
        stats = self.get_quick_stats()
        
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=5)
        )
        
        header_grid = Table.grid(expand=True)
        header_grid.add_column(justify="left")
        header_grid.add_column(justify="right")
        header_grid.add_row(
            "[bold white]GitHub Tuner[/bold white] [dim]Autonomous Agent[/dim]",
            f"Agent Status: [{status_color}]{status_text}[/{status_color}]"
        )
        layout["header"].update(Panel(header_grid, style="white on blue"))
        
        body_grid = Table(box=box.SIMPLE, expand=True)
        body_grid.add_column("Metric", style="cyan")
        body_grid.add_column("Value", style="bold white")
        
        body_grid.add_row("Inbox (Pending)", str(stats.get("pending", 0)))
        body_grid.add_row("Reviewed Today", str(stats.get("reviewed", 0)))
        body_grid.add_row("Active Mission", "General Exploration") # TODO: Load from mission.json
        
        layout["body"].update(Panel(body_grid, title="Mission Control"))
        
        footer_text = "[bold][s][/bold] Start/Stop Agent | [bold][r][/bold] Review Inbox | [bold][l][/bold] View Logs | [bold][q][/bold] Quit"
        layout["footer"].update(Panel(Align.center(footer_text), box=box.ROUNDED))
        
        self.console.print(layout)

    def get_quick_stats(self):
        # Quick and dirty sync DB check
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM findings WHERE status='pending'")
            pending = cursor.fetchone()[0]
            conn.close()
            return {"pending": pending, "reviewed": 0}
        except:
            return {"pending": "?", "reviewed": "?"}

    def toggle_agent(self):
        if self.agent_process and self.agent_process.poll() is None:
            self.agent_process.terminate()
            self.console.print("[yellow]Stopping agent...[/yellow]")
            time.sleep(1)
        else:
            # Spawn background process
            # python -m tuner.cli agent
            cmd = [sys.executable, "-m", "tuner.cli", "agent"]
            self.agent_process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.console.print("[green]Agent started in background![/green]")
            time.sleep(1)

    def run_review(self):
        # Delegate to review TUI
        # Run as subprocess to keep main clean, or invoke direct?
        # Direct invoke is better for TUI control
        from tuner.review_tui import ReviewTUI
        asyncio.run(ReviewTUI(self.db_path).run())

    def view_logs(self):
        self.console.print("[dim]Reading tuner.log (last 10 lines)...[/dim]")
        try:
            with open("tuner.log", "r") as f:
                lines = f.readlines()[-10:]
                for line in lines:
                    self.console.print(line.strip())
        except FileNotFoundError:
            self.console.print("[red]No log file found.[/red]")
        self.console.input("\nPress Enter to return...")

def main():
    menu = InteractiveMenu()
    menu.main_loop()

if __name__ == "__main__":
    main()
