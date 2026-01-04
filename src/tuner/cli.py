"""CLI for the GitHub Tuner"""
import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tuner.hunter import Hunter
from tuner.brain import LocalBrain, CloudBrain
from tuner.storage import TunerStorage
import numpy as np

app = typer.Typer(help="GitHub Tuner CLI")
console = Console()

DB_PATH = "data/tuner.db"
STRATEGY_PATH = "strategy.json"
USER_PROFILE_PATH = "data/user_profile.npy"

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

        with console.status("Analyzing and vectorizing...") as status:
            user_vector = local_brain.calculate_user_vector(descriptions)

        # Save vector
        os.makedirs(os.path.dirname(USER_PROFILE_PATH), exist_ok=True)
        np.save(USER_PROFILE_PATH, user_vector)
        console.print(f"[green]Analyzed {len(descriptions)} starred repos. Your interest profile is updated.[/green]")

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
    hunter = Hunter(STRATEGY_PATH)
    local_brain = LocalBrain()
    cloud_brain = CloudBrain()

    # Load user interests for screener
    if os.path.exists(USER_PROFILE_PATH):
        console.print("[green]Loading user interest profile...[/green]")
        interest_vector = np.load(USER_PROFILE_PATH)
    else:
        console.print("[yellow]No user profile found. Using strategy keywords...[/yellow]")
        strategy = hunter._load_strategy()
        keywords = " ".join(strategy.get("keywords", []))
        interest_vector = local_brain.vectorize(keywords)

    try:
        for i in range(iterations):
            console.print(f"\n[bold]Iteration {i+1}/{iterations}[/bold]")

            # 1. Hunter
            with console.status("Hunting for repositories...") as status:
                raw_findings = await hunter.search_github()
                status.update(f"Found {len(raw_findings)} raw candidates")

            console.print(f"  Found {len(raw_findings)} candidates.")

            count_screened = 0
            count_analyzed = 0

            # 2. Screener & 3. Analyst
            for finding in raw_findings:
                # Screen
                desc_vec = local_brain.vectorize(f"{finding.title} {finding.description}")
                similarity = local_brain.calculate_similarity(interest_vector, desc_vec)

                # Save first to get ID, now passing embedding
                f_id = storage.save_finding(
                    finding.title,
                    finding.url,
                    finding.description,
                    finding.stars,
                    finding.language,
                    embedding=desc_vec.tobytes()
                )

                if f_id == -1:
                     # Already exists
                     console.print(f"  [yellow]Skipped (duplicate): {finding.title}[/yellow]")
                     continue

                # If good match, Analyze
                if similarity >= min_score:
                    console.print(f"  [green]High Signal ({similarity:.2f}): {finding.title}[/green]")

                    with console.status(f"  Analyzing with CloudBrain...") as status:
                        summary, relevance = await cloud_brain.analyze_repo(finding.readme_content)

                    storage.update_finding_analysis(f_id, summary, relevance)
                    count_analyzed += 1
                else:
                    # Low score
                    storage.update_finding_analysis(f_id, "Filtered by Screener", similarity)

                count_screened += 1

            console.print(f"Processed {count_screened} items. Analyzed {count_analyzed} promising candidates.")

    finally:
        await hunter.close()

@app.command()
def list(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of findings to show"),
):
    """List pending findings."""
    storage = TunerStorage(DB_PATH)
    findings = storage.get_pending_findings()

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

@app.command()
def vote(
    finding_id: int = typer.Argument(..., help="ID of the finding"),
    vote: str = typer.Argument(..., help="'up' (like) or 'down' (dislike)"),
    star_on_github: bool = typer.Option(False, "--star-on-github", help="Star the repo on GitHub if liked"),
):
    """Vote on a finding to train the agent."""
    asyncio.run(_handle_vote(finding_id, vote, star_on_github))

async def _handle_vote(finding_id: int, vote: str, star_on_github: bool):
    storage = TunerStorage(DB_PATH)

    action = "like" if vote.lower() in ["up", "like", "+1"] else "dislike"
    status = "liked" if action == "like" else "disliked"

    storage.update_finding_status(finding_id, status)
    storage.log_feedback(finding_id, action)

    console.print(f"[green]Voted {action} on finding {finding_id}.[/green]")

    if action == "like" and star_on_github:
        finding = storage.get_finding(finding_id)
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

@app.command()
def optimize():
    """Optimize search strategy based on feedback."""
    asyncio.run(_optimize_strategy())

async def _optimize_strategy():
    storage = TunerStorage(DB_PATH)
    cloud_brain = CloudBrain()

    feedback = storage.get_feedback_history()
    if not feedback:
        console.print("[yellow]No feedback history found. Vote on findings first![/yellow]")
        return

    with console.status("Generating new strategy...") as status:
        new_strategy = await cloud_brain.generate_strategy(feedback)

    if new_strategy:
        storage.save_strategy(new_strategy)
        # Update strategy.json
        with open(STRATEGY_PATH, "w") as f:
            json.dump(new_strategy, f, indent=4)

        console.print(Panel(json.dumps(new_strategy, indent=2), title="New Strategy Applied"))
    else:
        console.print("[red]Failed to generate new strategy.[/red]")

if __name__ == "__main__":
    app()
