import sys
import os
import asyncio
import subprocess
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.prompt import Prompt, Confirm
from rich.align import Align
from rich import box
import time

from tuner.storage import TunerStorage

class InteractiveMenu:
    def __init__(self):
        self.console = Console()
        self.db_path = "data/tuner.db"
        self.missions_path = "missions.json"
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
            elif choice == 'p':
                self.show_report()
            elif choice == 'm':
                self.manage_missions()
            elif choice == 'o':
                self.run_optimization()
            elif choice == 'a':
                self.show_ai_usage()
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
        
        # Stats
        stats = self.get_quick_stats()
        missions = self.load_missions()
        
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=6)
        )
        
        header_grid = Table.grid(expand=True)
        header_grid.add_column(justify="left")
        header_grid.add_column(justify="right")
        header_grid.add_row(
            "[bold white]GitHub Tuner[/bold white] [dim]Autonomous Agent[/dim]",
            f"Agent: [{status_color}]{status_text}[/{status_color}]"
        )
        layout["header"].update(Panel(header_grid, style="white on blue"))
        
        body_grid = Table(box=box.SIMPLE, expand=True)
        body_grid.add_column("Metric", style="cyan")
        body_grid.add_column("Value", style="bold white")
        
        body_grid.add_row("📥 Inbox (Pending)", str(stats.get("pending", 0)))
        body_grid.add_row("📊 Total Findings", str(stats.get("total", 0)))
        body_grid.add_row("✅ AI Approved", str(stats.get("approved", 0)))
        body_grid.add_row("🎯 Active Missions", str(len(missions)))
        
        layout["body"].update(Panel(body_grid, title="📈 Dashboard"))
        
        footer_text = (
            "[bold][s][/bold] Start/Stop Agent  [bold][r][/bold] Review Inbox  [bold][p][/bold] Performance Report\n"
            "[bold][m][/bold] Manage Missions   [bold][o][/bold] Optimize  [bold][a][/bold] AI Usage  [bold][l][/bold] Logs  [bold][q][/bold] Quit"
        )
        layout["footer"].update(Panel(Align.center(footer_text), box=box.ROUNDED))
        
        self.console.print(layout)

    def get_quick_stats(self):
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM findings WHERE status='pending'")
            pending = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM findings")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM findings WHERE match_score > 0.25")
            approved = cursor.fetchone()[0]
            conn.close()
            return {"pending": pending, "total": total, "approved": approved}
        except:
            return {"pending": "?", "total": "?", "approved": "?"}

    def load_missions(self):
        try:
            with open(self.missions_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def save_missions(self, missions):
        with open(self.missions_path, "w", encoding="utf-8") as f:
            json.dump(missions, f, indent=4, ensure_ascii=False)

    def toggle_agent(self):
        if self.agent_process and self.agent_process.poll() is None:
            self.agent_process.terminate()
            self.console.print("[yellow]⏹ Stopping agent...[/yellow]")
            time.sleep(1)
        else:
            cmd = [sys.executable, "-m", "tuner.cli", "agent"]
            self.agent_process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.console.print("[green]▶ Agent started in new window![/green]")
            time.sleep(1)

    def run_review(self):
        from tuner.review_tui import ReviewTUI
        asyncio.run(ReviewTUI(self.db_path).run())

    def show_report(self):
        """Display performance report inline."""
        self.console.clear()
        self.console.print(Panel("[bold]📊 Performance Report[/bold]", style="blue"))
        
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Basic stats
            cursor.execute("SELECT COUNT(*) FROM findings")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM findings WHERE match_score > 0.25")
            approved = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM feedback_logs WHERE action='like'")
            likes = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM feedback_logs WHERE action='dislike'")
            dislikes = cursor.fetchone()[0]
            
            # Rejection reasons
            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM feedback_logs 
                WHERE action = 'dislike' AND category IS NOT NULL
                GROUP BY category ORDER BY count DESC
            """)
            rejection_cats = cursor.fetchall()
            
            conn.close()
            
            yield_rate = (approved / total * 100) if total > 0 else 0
            user_rate = (likes / (likes + dislikes) * 100) if (likes + dislikes) > 0 else 0
            
            table = Table(title="Metrics", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="bold white")
            table.add_row("Total Findings", str(total))
            table.add_row("AI Approved", f"{approved} ({yield_rate:.1f}%)")
            table.add_row("User Likes", str(likes))
            table.add_row("User Dislikes", str(dislikes))
            table.add_row("User Acceptance", f"{user_rate:.1f}%")
            self.console.print(table)
            
            if rejection_cats:
                rej_table = Table(title="❌ Rejection Categories", box=box.SIMPLE)
                rej_table.add_column("Category", style="red")
                rej_table.add_column("Count", style="white")
                for cat, count in rejection_cats:
                    rej_table.add_row(cat or "unspecified", str(count))
                self.console.print(rej_table)
                
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
        
        self.console.input("\n[dim]Press Enter to return...[/dim]")

    def manage_missions(self):
        """Mission management sub-menu."""
        while True:
            self.console.clear()
            missions = self.load_missions()
            
            self.console.print(Panel("[bold]🎯 Mission Manager[/bold]", style="blue"))
            
            # Display current missions
            table = Table(title=f"{len(missions)} Active Missions", box=box.ROUNDED)
            table.add_column("#", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Seed Repos", style="white")
            table.add_column("Languages", style="green")
            table.add_column("Constraints", style="yellow")
            
            for i, m in enumerate(missions, 1):
                langs = ", ".join(m.get("languages", []))[:15]
                # Show seed repos instead of raw query
                seed_preview = "No seeds"
                if m.get("seed_repos"):
                    seed_preview = ", ".join([r.split("/")[-1] for r in m["seed_repos"]])[:25]
                elif m.get("goal"):
                    seed_preview = f"Query: {m['goal'][:20]}"

                constraints = []
                if m.get("min_stars"): constraints.append(f"⭐>{m['min_stars']}")
                if m.get("max_days_since_commit"): constraints.append(f"📅<{m['max_days_since_commit']}d")
                constraint_str = ", ".join(constraints) if constraints else "None"
                
                table.add_row(str(i), m["name"], seed_preview, langs, constraint_str)
            
            self.console.print(table)
            
            self.console.print("\n[bold][1][/bold] Add Mission  [bold][2][/bold] Edit Mission  [bold][3][/bold] Delete Mission  [bold][b][/bold] Back")
            choice = self.console.input("\n[bold blue]Mission Command > [/bold blue]").strip().lower()
            
            if choice == '1':
                self.add_mission(missions)
            elif choice == '2':
                self.edit_mission(missions)
            elif choice == '3':
                self.delete_mission(missions)
            elif choice == 'b':
                break

    def add_mission(self, missions):
        self.console.print("\n[bold green]➕ Add New Mission[/bold green]")
        name = Prompt.ask("Mission Name (e.g. 'Uncommon React Tools')")
        
        # New: Seed repositories
        seed_input = Prompt.ask("Seed Repos (comma-sep owner/repo, optional)", default="")
        seed_repos = [s.strip() for s in seed_input.split(",")] if seed_input.strip() else []
        
        # New: User notes
        user_notes = Prompt.ask("Research Notes (Describe what you want)", default="Find interesting tools")
        
        # Fallback Keywords (AI will generate, but good to have)
        goal = Prompt.ask("Keywords (Fallback)", default=name.lower())
        
        languages = Prompt.ask("Languages (comma-separated)", default="Python")
        
        # Optional constraints
        min_stars = Prompt.ask("Min Stars (0 for none)", default="0")
        max_days = Prompt.ask("Max Days Since Commit (Empty for any)", default="")
        
        new_mission = {
            "name": name,
            "goal": goal,
            "languages": [l.strip() for l in languages.split(",")],
            "min_stars": int(min_stars),
            "max_days_since_commit": int(max_days) if max_days.strip() else None,
            "seed_repos": seed_repos,
            "user_notes": user_notes,
            "context_path": None
        }
        missions.append(new_mission)
        self.save_missions(missions)
        self.console.print(f"[green]✅ Mission '{name}' added![/green]")
        time.sleep(1)

    def edit_mission(self, missions):
        if not missions:
            self.console.print("[yellow]No missions to edit.[/yellow]")
            time.sleep(1)
            return
        
        idx = Prompt.ask("Enter mission number to edit", default="1")
        try:
            idx = int(idx) - 1
            if 0 <= idx < len(missions):
                m = missions[idx]
                self.console.print(f"\n[bold]Editing: {m['name']}[/bold]")
                
                m["name"] = Prompt.ask("Name", default=m["name"])
                
                # Edit Seed Repos
                curr_seeds = ", ".join(m.get("seed_repos", []) or [])
                new_seeds = Prompt.ask("Seed Repos", default=curr_seeds)
                m["seed_repos"] = [s.strip() for s in new_seeds.split(",")] if new_seeds.strip() else []
                
                # Edit Notes
                m["user_notes"] = Prompt.ask("Notes", default=m.get("user_notes", ""))
                
                m["goal"] = Prompt.ask("Keywords", default=m["goal"])
                
                langs = ", ".join(m.get("languages", []))
                new_langs = Prompt.ask("Languages", default=langs)
                m["languages"] = [l.strip() for l in new_langs.split(",")]
                
                m["min_stars"] = int(Prompt.ask("Min Stars", default=str(m.get("min_stars", 0))))
                
                curr_days = str(m.get("max_days_since_commit") or "")
                new_days = Prompt.ask("Max Days Inactive", default=curr_days)
                m["max_days_since_commit"] = int(new_days) if new_days.strip() else None
                
                # Reset init flag if significantly changed
                if Confirm.ask("Reset AI Strategy for this mission?"):
                    m["initialized"] = False
                    m["ai_strategy"] = None
                
                self.save_missions(missions)
                self.console.print("[green]✅ Mission updated![/green]")
            else:
                self.console.print("[red]Invalid number.[/red]")
        except ValueError:
            self.console.print("[red]Invalid input.[/red]")
        time.sleep(1)

    def delete_mission(self, missions):
        if not missions:
            self.console.print("[yellow]No missions to delete.[/yellow]")
            time.sleep(1)
            return
        
        idx = Prompt.ask("Enter mission number to delete")
        try:
            idx = int(idx) - 1
            if 0 <= idx < len(missions):
                name = missions[idx]["name"]
                if Confirm.ask(f"Delete '{name}'?"):
                    missions.pop(idx)
                    self.save_missions(missions)
                    self.console.print(f"[red]🗑 Mission '{name}' deleted.[/red]")
            else:
                self.console.print("[red]Invalid number.[/red]")
        except ValueError:
            self.console.print("[red]Invalid input.[/red]")
        time.sleep(1)

    def show_ai_usage(self):
        """Display AI usage statistics."""
        self.console.clear()
        self.console.print(Panel("[bold]🤖 AI Usage Statistics[/bold]", style="blue"))
        
        import sqlite3
        from datetime import datetime, timedelta
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total calls
            cursor.execute("SELECT COUNT(*) FROM ai_usage")
            total_calls = cursor.fetchone()[0]
            
            # Successful vs failed
            cursor.execute("SELECT COUNT(*) FROM ai_usage WHERE success = 1")
            successful = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM ai_usage WHERE success = 0")
            failed = cursor.fetchone()[0]
            
            # Total tokens (estimated)
            cursor.execute("SELECT SUM(tokens_in), SUM(tokens_out) FROM ai_usage WHERE success = 1")
            row = cursor.fetchone()
            tokens_in = row[0] or 0
            tokens_out = row[1] or 0
            
            # By call type
            cursor.execute("""
                SELECT call_type, COUNT(*), SUM(tokens_in), SUM(tokens_out), AVG(duration_ms)
                FROM ai_usage
                GROUP BY call_type
            """)
            by_type = cursor.fetchall()
            
            # Rate limit errors
            cursor.execute("SELECT COUNT(*) FROM ai_usage WHERE error_type = 'rate_limit'")
            rate_limits = cursor.fetchone()[0]
            
            # Last 24 hours
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cursor.execute(f"SELECT COUNT(*) FROM ai_usage WHERE timestamp > '{yesterday}'")
            last_24h = cursor.fetchone()[0]
            
            # Recent errors
            cursor.execute("""
                SELECT call_type, error_type, timestamp 
                FROM ai_usage 
                WHERE success = 0 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            recent_errors = cursor.fetchall()
            
            conn.close()
            
            # Display stats
            table = Table(title="📊 Overview", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="bold white")
            table.add_row("Total AI Calls", str(total_calls))
            table.add_row("Successful", f"[green]{successful}[/green]")
            table.add_row("Failed", f"[red]{failed}[/red]")
            table.add_row("Rate Limit Hits", f"[yellow]{rate_limits}[/yellow]")
            table.add_row("Last 24 Hours", str(last_24h))
            table.add_row("", "")
            table.add_row("Est. Tokens In", f"{tokens_in:,}")
            table.add_row("Est. Tokens Out", f"{tokens_out:,}")
            table.add_row("Total Tokens", f"[bold]{tokens_in + tokens_out:,}[/bold]")
            self.console.print(table)
            
            # By call type
            if by_type:
                type_table = Table(title="📞 By Call Type", box=box.SIMPLE)
                type_table.add_column("Type", style="cyan")
                type_table.add_column("Count", style="white")
                type_table.add_column("Tokens In", style="dim")
                type_table.add_column("Tokens Out", style="dim")
                type_table.add_column("Avg Duration", style="green")
                for ct, count, ti, to, dur in by_type:
                    type_table.add_row(
                        ct, str(count), 
                        str(ti or 0), str(to or 0),
                        f"{int(dur or 0)}ms"
                    )
                self.console.print(type_table)
            
            # Recent errors
            if recent_errors:
                self.console.print("\n[bold red]❌ Recent Errors:[/bold red]")
                for call_type, error_type, ts in recent_errors:
                    self.console.print(f"  • {ts[:19]} | {call_type} | [red]{error_type}[/red]")
            
            # Explanation
            self.console.print("\n[dim]Note: Token counts are estimates (4 chars ≈ 1 token)[/dim]")
            self.console.print("[dim]Context sent to AI: README (max 5000 chars) + prompt template[/dim]")
            
        except Exception as e:
            self.console.print(f"[red]Error reading AI usage: {e}[/red]")
            self.console.print("[dim]AI usage table may not exist yet. Run the agent first.[/dim]")
        
        self.console.input("\n[dim]Press Enter to return...[/dim]")

    def run_optimization(self):
        """Run AI strategy optimization in new terminal window."""
        self.console.print("[cyan]🧠 Starting AI Strategy Optimization in new window...[/cyan]")
        cmd = [sys.executable, "-m", "tuner.cli", "optimize"]
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.console.print("[green]✅ Optimization started! Check the new terminal window.[/green]")
        time.sleep(2)

    def view_logs(self):
        self.console.clear()
        self.console.print(Panel("[bold]📋 Recent Logs[/bold]", style="blue"))
        try:
            with open("tuner.log", "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-20:]
                for line in lines:
                    # Clean up and display
                    clean = line.strip()
                    if "[INFO]" in clean:
                        self.console.print(f"[green]{clean}[/green]")
                    elif "[WARNING]" in clean:
                        self.console.print(f"[yellow]{clean}[/yellow]")
                    elif "[ERROR]" in clean:
                        self.console.print(f"[red]{clean}[/red]")
                    else:
                        self.console.print(f"[dim]{clean}[/dim]")
        except FileNotFoundError:
            self.console.print("[red]No log file found.[/red]")
        self.console.input("\n[dim]Press Enter to return...[/dim]")

def main():
    menu = InteractiveMenu()
    menu.main_loop()

if __name__ == "__main__":
    main()
