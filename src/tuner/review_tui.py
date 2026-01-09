from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich import box
from rich.live import Live
import asyncio
import webbrowser
from typing import List, Dict, Any

from tuner.storage import TunerStorage
from tuner.brain import LocalBrain # Just for accessing utilities if needed

class ReviewTUI:
    def __init__(self, db_path="data/tuner.db"):
        self.storage = TunerStorage(db_path)
        self.console = Console()
        self.findings = []
        self.current_index = 0

    async def run(self):
        """Run the interactive review session."""
        await self.storage.initialize()
        
        # Load findings marked as "Pending Review" (or high score but not Feedback'd)
        # We need a proper way to query 'Inbox'. For now, let's grab top pending.
        self.findings = await self.storage.get_pending_findings()
        
        if not self.findings:
            self.console.print("[yellow]Inbox is empty! Nothing to review.[/yellow]")
            return

        while True:
            await self.show_finding()
            
            # Simple input loop (Blocking, but okay for this TUI mode)
            choice = self.console.input("\n[bold]Action ([green]y[/]/[red]n[/]/[blue]o[/]pen/[yellow]q[/]uit): [/bold]").lower().strip()
            
            if choice == 'q':
                break
            elif choice == 'o':
                url = self.findings[self.current_index]['url']
                webbrowser.open(url)
            elif choice == 'y':  # Like
                await self.submit_feedback("up")
            elif choice == 'n':  # Dislike
                await self.submit_feedback("down")
            
            # Advance
            # (If we voted, we remove it or just show next? Let's just go next index for now, usually we'd pop)
            if choice in ['y', 'n']:
                 self.current_index += 1
            
            if self.current_index >= len(self.findings):
                self.console.print("[green]All items reviewed![/green]")
                break
                
        await self.storage.close()

    async def show_finding(self):
        self.console.clear()
        
        if self.current_index >= len(self.findings):
            return

        item = self.findings[self.current_index]
        
        # Header
        self.console.print(Panel(f"[bold blue]Review Inbox ({self.current_index + 1}/{len(self.findings)})[/bold blue]", box=box.HEAVY))
        
        # Content
        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_row(f"[bold]Title:[/bold] {item['title']}")
        grid.add_row(f"[bold]Language:[/bold] {item.get('language', 'Unknown')}")
        grid.add_row(f"[bold]Stars:[/bold] {item.get('stars', 0)}")
        grid.add_row(f"[bold]URL:[/bold] [link={item['url']}]{item['url']}[/link]")
        grid.add_row("")
        grid.add_row(Panel(item.get("description", "No description"), title="Description", border_style="green"))
        
        if item.get("ai_summary"):
             grid.add_row(Panel(item["ai_summary"], title="Gemini Analysis", border_style="magenta"))

        self.console.print(grid)

    async def submit_feedback(self, vote_type: str):
        item = self.findings[self.current_index]
        action = "like" if vote_type == "up" else "dislike"
        status = "liked" if action == "like" else "disliked"
        
        await self.storage.update_finding_status(item['id'], status)
        await self.storage.log_feedback(item['id'], action)
