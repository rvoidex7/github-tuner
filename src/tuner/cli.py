"""CLI for the GitHub Tuner"""
import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Optional, List
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

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show the application version and exit.", callback=version_callback, is_eager=True
    )
):
    """
    GitHub Tuner: AI-powered repository discovery.
    """
    pass

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

    # Load user interests for screener
    interest_clusters = []
    if os.path.exists(USER_PROFILE_PATH):
        console.print("[green]Loading user interest profile...[/green]")
        try:
            interest_clusters = np.load(USER_PROFILE_PATH)
            # Ensure it's 2D array (k, dim)
            if len(interest_clusters.shape) == 1:
                interest_clusters = interest_clusters.reshape(1, -1)
        except Exception:
            console.print("[red]Failed to load profile. Re-run init.[/red]")

    if len(interest_clusters) == 0:
        console.print("[yellow]No user profile found. Using strategy keywords...[/yellow]")
        strategy = hunter._load_strategy()
        keywords = " ".join(strategy.get("keywords", []))
        interest_clusters = [local_brain.vectorize(keywords)]

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

                # Check against ALL clusters and take MAX similarity
                max_similarity = 0.0
                for cluster_vec in interest_clusters:
                    sim = local_brain.calculate_similarity(cluster_vec, desc_vec)
                    if sim > max_similarity:
                        max_similarity = sim

                similarity = max_similarity

                # Save first to get ID, now passing embedding
                f_id = await storage.save_finding(
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

                    await storage.update_finding_analysis(f_id, summary, relevance)
                    count_analyzed += 1
                else:
                    # Low score
                    await storage.update_finding_analysis(f_id, "Filtered by Screener", similarity)

                count_screened += 1

            console.print(f"Processed {count_screened} items. Analyzed {count_analyzed} promising candidates.")

    finally:
        await hunter.close()
        await storage.close()

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
    star_on_github: bool = typer.Option(False, "--star-on-github", help="Star the repo on GitHub if liked"),
):
    """Vote on a finding to train the agent."""
    asyncio.run(_handle_vote(finding_id, vote, star_on_github))

async def _handle_vote(finding_id: int, vote: str, star_on_github: bool):
    storage = TunerStorage(DB_PATH)
    await storage.initialize()
    local_brain = LocalBrain()

    try:
        action = "like" if vote.lower() in ["up", "like", "+1"] else "dislike"
        status = "liked" if action == "like" else "disliked"

        await storage.update_finding_status(finding_id, status)
        await storage.log_feedback(finding_id, action)

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
def optimize():
    """Optimize search strategy based on feedback."""
    asyncio.run(_optimize_strategy())

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
    app()
