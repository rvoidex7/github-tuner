"""CLI for the GitHub patch scraper"""
import asyncio
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scraper.fetcher import fetch_patch
from scraper.parser import parse_patch, is_noreply_email
from scraper.storage import PatchStorage
from scraper.discover import GitHubDiscovery

app = typer.Typer(help="GitHub .patch scraper CLI")
console = Console()


@app.command()
def fetch(
    url: str = typer.Argument(..., help="URL to the .patch file"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="GitHub token for auth"),
    db_path: str = typer.Option("data/patches.db", "--db", help="Path to SQLite database"),
):
    """Fetch and parse a .patch URL, store in database."""
    asyncio.run(_fetch_and_store(url, token, db_path))


async def _fetch_and_store(url: str, token: Optional[str], db_path: str):
    storage = PatchStorage(db_path)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Fetching {url}...", total=None)
        
        try:
            # Fetch
            raw_patch = await fetch_patch(url, token=token)
            progress.update(task, description=f"Parsing {url}...")
            
            # Parse line 2
            try:
                parsed = parse_patch(raw_patch)
                email = parsed["email"]
                username = parsed["username"]
            except Exception as e:
                console.print(f"[red]✗ Parse error: {e}[/red]")
                raise typer.Exit(code=1)
            
            # Rule 2: Skip noreply emails
            if is_noreply_email(email):
                console.print(f"[yellow]⊘ Skipped: noreply email ({email})[/yellow]")
                return
            
            # Rule 1: Skip if email already exists
            if storage.email_exists(email):
                console.print(f"[yellow]⊘ Skipped: email already in database ({email})[/yellow]")
                return
            
            # Store
            progress.update(task, description=f"Storing {email}...")
            row_id = storage.save_patch(email, username)
            
            progress.update(task, description=f"✓ Saved (id={row_id})")
            console.print(f"[green]✓ Saved to database (id={row_id})[/green]")
            console.print(f"  Email: {email}")
            console.print(f"  Username: {username}")
        
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def list_patches(
    db_path: str = typer.Option("data/patches.db", "--db", help="Path to SQLite database"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of patches to list"),
):
    """List emails and usernames in the database."""
    storage = PatchStorage(db_path)
    patches = storage.list_patches(limit=limit)
    
    if not patches:
        console.print("[yellow]No records found in database.[/yellow]")
        return
    
    total = storage.count_patches()
    console.print(f"[bold]Recent records (showing {len(patches)} of {total} total):[/bold]\n")
    for patch in patches:
        console.print(f"  ID: {patch['id']}")
        console.print(f"  Email: {patch['email']}")
        console.print(f"  Username: {patch['username']}")
        console.print(f"  Created: {patch['created_at']}")
        console.print()


@app.command()
def auto_fetch(
    count: int = typer.Option(10, "--count", "-n", help="Number of patches to fetch"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="GitHub token for auth (highly recommended)"),
    db_path: str = typer.Option("data/patches.db", "--db", help="Path to SQLite database"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language (random if not set)"),
    topic: Optional[str] = typer.Option(None, "--topic", help="Filter by topic (random if not set)"),
    mode: str = typer.Option("random", "--mode", "-m", help="Mode: 'random' or 'popular'"),
):
    """Automatically discover and fetch random GitHub commits."""
    asyncio.run(_auto_fetch_patches(count, token, db_path, language, topic, mode))


async def _auto_fetch_patches(
    count: int,
    token: Optional[str],
    db_path: str,
    language: Optional[str],
    topic: Optional[str],
    mode: str
):
    """Auto-fetch patches from GitHub."""
    storage = PatchStorage(db_path)
    discovery = GitHubDiscovery(token=token)
    
    console.print(f"[bold]🚀 Auto-fetching {count} patches (mode: {mode})[/bold]")
    console.print()
    
    if not token:
        console.print("[yellow]⚠️  No token provided. Rate limits apply (60 req/hour).[/yellow]")
        console.print("[yellow]   Use --token for higher limits (5000 req/hour).[/yellow]")
        console.print()
    
    fetched = 0
    skipped = 0
    errors = 0
    
    try:
        # Discover patches
        if mode == "popular":
            patch_generator = discovery.discover_from_popular_repos(count=count)
        else:
            patch_generator = discovery.discover_random_patches(
                count=count,
                language=language,
                topic=topic
            )
        
        console.print()
        
        # Fetch each discovered patch
        async for patch_url in patch_generator:
            try:
                console.print(f"📥 Fetching: {patch_url}")
                
                # Fetch
                raw_patch = await fetch_patch(patch_url, token=token, max_retries=2)
                
                # Parse
                parsed = parse_patch(raw_patch)
                email = parsed["email"]
                username = parsed["username"]
                
                # Apply filtering rules
                if is_noreply_email(email):
                    console.print(f"   [yellow]⊘ Skipped: noreply email[/yellow]")
                    skipped += 1
                    continue
                
                if storage.email_exists(email):
                    console.print(f"   [yellow]⊘ Skipped: duplicate email[/yellow]")
                    skipped += 1
                    continue
                
                # Save
                row_id = storage.save_patch(email, username)
                console.print(f"   [green]✓ Saved (id={row_id}): {email} ({username})[/green]")
                fetched += 1
                
            except Exception as e:
                console.print(f"   [red]✗ Error: {e}[/red]")
                errors += 1
            
            # Small delay between requests
            await asyncio.sleep(0.3)
        
        console.print()
        console.print("[bold]Summary:[/bold]")
        console.print(f"  ✓ Fetched: {fetched}")
        console.print(f"  ⊘ Skipped: {skipped}")
        console.print(f"  ✗ Errors: {errors}")
        console.print()
        
        total = storage.count_patches()
        console.print(f"[bold]📊 Total emails in database: {total}[/bold]")
    
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]⚠️  Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Fatal error: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
```


if __name__ == "__main__":
    app()
