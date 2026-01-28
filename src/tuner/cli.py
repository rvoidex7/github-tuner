"""CLI for the GitHub Tuner"""
import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tuner.hunter import Hunter
from tuner.brain import LocalBrain, CloudBrain
from tuner.storage import TunerStorage
from tuner.tui import TunerDashboard, TuiLogHandler
from tuner.manager import AutonomousManager
from tuner.workers import WorkerManager
from tuner.menu import main as menu_main
from rich.live import Live
import numpy as np
import logging

HELP_TEXT = """
# GitHub Tuner 🧬

**An Autonomous, Hybrid-AI Repository Discovery Agent.**

This tool acts as your personal research assistant, finding and filtering GitHub repositories
that match your specific interests. It uses a hybrid approach:

*   **Hunter**: Scans GitHub for fresh repositories using dynamic strategies.
*   **Screener**: Uses **Local AI** (Embeddings) to filter noise based on your clustered interest profile.
*   **Analyst**: Uses **Cloud AI** (Gemini) to score and summarize the top candidates.
*   **Manager**: Learns from your feedback (votes) to continuously improve search accuracy.

**Getting Started:**
1.  Run `init` to analyze your stars and create an interest profile.
2.  Run `start` to begin the discovery loop.
3.  Run `list` to see what was found.
4.  Run `vote` to train the agent.
"""

app = typer.Typer(
    help=HELP_TEXT,
    rich_markup_mode="markdown",
    context_settings={"help_option_names": ["-h", "--help"]}
)
console = Console()

DB_PATH = "data/tuner.db"
STRATEGY_PATH = "strategy.json"
USER_PROFILE_PATH = "data/user_profile.npy"

def version_callback(value: bool):
    if value:
        console.print("[bold blue]GitHub Tuner[/bold blue] v0.3.0 (Phase 3)")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show the application version and exit.", callback=version_callback, is_eager=True
    ),
    ctx: typer.Context = None
):
    """
    GitHub Tuner: AI-powered repository discovery.
    """
    if ctx.invoked_subcommand is None:
        menu_main()

@app.command()
def agent():
    """Start the autonomous background agent (worker mode)."""
    asyncio.run(_run_agent())

async def _run_agent():
    console.print(Panel.fit("[bold blue]GitHub Tuner[/bold blue] 👷 Starting Background Mission Agent..."))

    # Configure Logging (Force Reconfigure)
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
    
    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    fh = logging.FileHandler("tuner.log", mode='a', encoding='utf-8')
    fh.setFormatter(formatter)
    root.addHandler(fh)
    
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root.addHandler(sh)

    # Initialize Autonomous Manager (Supports Missions)
    manager = AutonomousManager(db_path=DB_PATH, strategy_path=STRATEGY_PATH, mission_path="missions.json")

    try:
        await manager.start()
    except KeyboardInterrupt:
        console.print("[yellow]Stopping agent...[/yellow]")
        manager.stop()
    except Exception as e:
        console.print(f"[red]Agent crashed: {e}[/red]")
        logging.exception("Agent crashed")

@app.command()
def reset():
    """Reset the database (clear all findings and history)."""
    asyncio.run(_reset_db())

async def _reset_db():
    storage = TunerStorage(DB_PATH)
    console.print(Panel.fit("[bold red]GitHub Tuner[/bold red] 🗑️ Resetting Database..."))
    try:
        await storage.reset_database()
        console.print("[green]Database has been reset successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Failed to reset database: {e}[/red]")

@app.command()
def init():
    """Initialize user profile by analyzing starred repos."""
    asyncio.run(_init_profile())

async def _init_profile():
    console.print(Panel.fit("[bold blue]GitHub Tuner[/bold blue] 🧬 Initializing User Profile..."))

    hunter = Hunter(STRATEGY_PATH)
    local_brain = LocalBrain()

    try:
        with console.status("Fetching starred repositories...") as status:
            descriptions = await hunter.fetch_user_starred_repos(limit=100)
            status.update(f"Fetched {len(descriptions)} starred repos.")

        if not descriptions:
            console.print("[yellow]No starred repos found or token missing. Skipping profile generation.[/yellow]")
            return

        with console.status("Clustering interests...") as status:
            clusters = local_brain.generate_interest_clusters(descriptions, k=5)

        # Save clusters (list of vectors)
        os.makedirs(os.path.dirname(USER_PROFILE_PATH), exist_ok=True)
        np.save(USER_PROFILE_PATH, np.array(clusters))
        console.print(f"[green]Analyzed {len(descriptions)} starred repos. Identified {len(clusters)} interest clusters.[/green]")

    finally:
        await hunter.close()

@app.command()
def start(
    iterations: int = typer.Option(1, "--iterations", "-i", help="Number of search iterations"),
    min_score: float = typer.Option(0.4, "--min-score", "-s", help="Minimum similarity score to trigger CloudBrain"),
):
    """Start the tuning process: Hunter -> Screener -> Analyst."""
    asyncio.run(_run_tuning_loop(iterations, min_score))

async def _run_tuning_loop(iterations: int, min_score: float):
    console.print(Panel.fit("[bold blue]GitHub Tuner[/bold blue] 🚀 Starting discovery engine..."))

    storage = TunerStorage(DB_PATH)
    await storage.initialize() # Ensure DB is ready

    hunter = Hunter(STRATEGY_PATH)
    local_brain = LocalBrain()
    cloud_brain = CloudBrain()

    # Setup TUI
    dashboard = TunerDashboard(console)
    
    # Configure Logging (File + TUI)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("tuner.log", mode='a', encoding='utf-8'),
            TuiLogHandler(dashboard)
        ]
    )
    
    # Initialize Autonomous Manager
    manager = AutonomousManager(db_path=DB_PATH, strategy_path=STRATEGY_PATH, mission_path="missions.json")

    with Live(dashboard, refresh_per_second=4, screen=True) as live:
        try:
            dashboard.update_status("Starting Autonomous Manager...")
            
            # Run Manager in background task
            mgr_task = asyncio.create_task(manager.start())
            
            # Run UI Loop to update stats
            while not mgr_task.done():
                dashboard.update_status("Running Missions...")
                # Update stats from manager
                dashboard.update_stats(
                    scanned=manager.session_stats["scanned"],
                    analyzed=manager.session_stats["interested"]
                )
                
                # We could pull findings from DB or have manager emit them.
                # For now, just rely on logs.
                 
                # Update current mission in UI if possible
                if manager.mission_control.current_mission:
                     dashboard.iteration_info = f"Mission: {manager.mission_control.current_mission.name}"
                
                await asyncio.sleep(0.5)
            
            await mgr_task
            
        except KeyboardInterrupt:
            dashboard.update_status("Stopping...")
            manager.stop()
            await mgr_task
            
        finally:
            dashboard.update_status("Shutting down...")
            logging.getLogger().handlers = [] # Clear handlers

    # Post-TUI Summary (Simplified for now as Manager runs indefinitely)
    console.print("\n[bold green]🚀 Session Complete[/bold green]")
    console.print(f"[dim]Detailed logs written to 'tuner.log'[/dim]\n")

@app.command()
def list(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of findings to show"),
):
    """List pending findings."""
    asyncio.run(_list_findings(limit))

async def _list_findings(limit: int):
    storage = TunerStorage(DB_PATH)
    await storage.initialize()
    try:
        findings = await storage.get_pending_findings()

        table = Table(title=f"Top Pending Findings ({len(findings)} total)")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Score", style="magenta")
        table.add_column("Title", style="bold")
        table.add_column("Summary")

        for f in findings[:limit]:
            table.add_row(
                str(f["id"]),
                f"{f['match_score']:.2f}" if f['match_score'] else "N/A",
                f"[link={f['url']}]{f['title']}[/link]",
                f["ai_summary"][:100] + "..." if f["ai_summary"] else ""
            )

        console.print(table)
    finally:
        await storage.close()

@app.command()
def vote(
    finding_id: int = typer.Argument(..., help="ID of the finding"),
    vote: str = typer.Argument(..., help="'up' (like) or 'down' (dislike)"),
    category: str = typer.Option(None, "--category", "-c", help="Category: relevant_good, relevant_bad, irrelevant, off_topic"),
    reason: str = typer.Option(None, "--reason", "-r", help="Free text reason for the vote"),
    star_on_github: bool = typer.Option(False, "--star-on-github", help="Star the repo on GitHub if liked"),
):
    """Vote on a finding to train the agent."""
    asyncio.run(_handle_vote(finding_id, vote, category, reason, star_on_github))

async def _handle_vote(finding_id: int, vote: str, category: str, reason: str, star_on_github: bool):
    storage = TunerStorage(DB_PATH)
    await storage.initialize()
    local_brain = LocalBrain()

    try:
        action = "like" if vote.lower() in ["up", "like", "+1"] else "dislike"
        status = "liked" if action == "like" else "disliked"

        await storage.update_finding_status(finding_id, status)
        await storage.log_feedback(finding_id, action, category, reason)

        console.print(f"[green]Voted {action} on finding {finding_id}.[/green]")

        # Dynamic Learning (Nudge)
        if action == "like" and os.path.exists(USER_PROFILE_PATH):
            try:
                finding = await storage.get_finding(finding_id)
                if finding:
                    # Reconstruct vector from title/desc (simplest way without decoding blob properly yet)
                    # Ideally we store vector properly or decode blob
                    desc_vec = local_brain.vectorize(f"{finding['title']} {finding['description']}")

                    clusters = np.load(USER_PROFILE_PATH)
                    if len(clusters.shape) == 1: clusters = clusters.reshape(1, -1)

                    # Find closest cluster
                    best_idx = -1
                    max_sim = -1.0
                    for i, c in enumerate(clusters):
                        sim = local_brain.calculate_similarity(c, desc_vec)
                        if sim > max_sim:
                            max_sim = sim
                            best_idx = i

                    if best_idx != -1:
                        # Nudge cluster center towards new repo (Learning Rate: 0.1)
                        learning_rate = 0.1
                        clusters[best_idx] = (1 - learning_rate) * clusters[best_idx] + learning_rate * desc_vec
                        np.save(USER_PROFILE_PATH, clusters)
                        console.print(f"[blue]🧠 Brain updated: Interest cluster {best_idx} adjusted.[/blue]")
            except Exception as e:
                console.print(f"[red]Failed to update brain: {e}[/red]")

        if action == "like" and star_on_github:
            finding = await storage.get_finding(finding_id)
            if finding and finding.get("url"):
                # Parse owner/repo from URL (https://github.com/owner/repo)
                url = finding["url"]
                try:
                    # Remove .git suffix if present
                    if url.endswith(".git"):
                        url = url[:-4]

                    parts = url.rstrip("/").split("/")
                    if len(parts) >= 2:
                        repo = parts[-1]
                        owner = parts[-2]

                        # Basic validation of owner/repo names
                        if not owner or not repo or "." in owner: # Simple heuristic check
                             console.print(f"[red]Could not parse valid owner/repo from URL: {url}[/red]")
                             return

                        hunter = Hunter()
                        try:
                            if await hunter.star_repo(owner, repo):
                                 console.print(f"[green]Successfully starred {owner}/{repo} on GitHub![/green]")
                            else:
                                 console.print(f"[red]Failed to star {owner}/{repo} on GitHub.[/red]")
                        finally:
                            await hunter.close()
                    else:
                         console.print(f"[red]Invalid GitHub URL format: {url}[/red]")
                except Exception as e:
                     console.print(f"[red]Error parsing URL {url}: {e}[/red]")
            else:
                 console.print("[red]Could not determine repo URL for starring.[/red]")
    finally:
        await storage.close()

@app.command()
def report():
    """Show the Agent's Self-Learning Report Card."""
    from tuner.analytics import AnalyticsEngine
    
    async def _show_report():
        engine = AnalyticsEngine(DB_PATH)
        report = await engine.generate_report()
        
        # 1. Yield Rates
        yields = report["yield_rates"]
        table = Table(title="📊 Performance Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Total Findings", str(yields['total_findings']))
        table.add_row("AI Approved", f"{yields['ai_approved']} (Yield: {yields['ai_yield']:.1%})")
        table.add_row("User Acceptance", f"{yields['user_acceptance_rate']:.1%}")
        console.print(table)
        
        # 2. Rejection Analysis
        rejected = report["rejection_analysis"]
        if rejected["by_category"]:
            table = Table(title="❌ Rejection Reasons")
            table.add_column("Category", style="red")
            table.add_column("Count", style="white")
            for item in rejected["by_category"]:
                table.add_row(item['category'] or "Uncategorized", str(item['count']))
            console.print(table)
            
        if rejected["common_reasons"]:
            console.print("\n[bold red]📝 Common Complaints:[/bold red]")
            for item in rejected["common_reasons"]:
                 console.print(f"- {item['reason']} ({item['count']}x)")

    asyncio.run(_show_report())

@app.command()
def optimize():
    """Optimize search strategy based on feedback."""
    asyncio.run(_optimize_strategy())

@app.command()
def engineer(
    mission: str = typer.Argument(..., help="The goal of the engineering mission"),
):
    """Launch the Autonomous Software Engineer TUI."""
    from tuner.agent.core import EngineerAgent
    from tuner.agent.ui import AgentDashboard

    # Initialize Agent
    agent = EngineerAgent(DB_PATH)

    # Launch UI
    app = AgentDashboard(agent, mission)
    app.run()

async def _optimize_strategy():
    storage = TunerStorage(DB_PATH)
    await storage.initialize()
    cloud_brain = CloudBrain()

    try:
        feedback = await storage.get_feedback_history()
        if not feedback:
            console.print("[yellow]No feedback history found. Vote on findings first![/yellow]")
            return

        with console.status("Generating new strategy...") as status:
            new_strategy = await cloud_brain.generate_strategy(feedback)

        if new_strategy:
            await storage.save_strategy(new_strategy)
            # Update strategy.json
            with open(STRATEGY_PATH, "w") as f:
                json.dump(new_strategy, f, indent=4)

            console.print(Panel(json.dumps(new_strategy, indent=2), title="New Strategy Applied"))
        else:
            console.print("[red]Failed to generate new strategy.[/red]")
    finally:
        await storage.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app()
