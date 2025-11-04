"""Discover random GitHub commits and PRs for scraping"""
import asyncio
import random
from typing import List, Optional, AsyncGenerator
import httpx


class GitHubDiscovery:
    """Discover random GitHub commits and generate .patch URLs."""
    
    # Popular programming languages for diversity
    LANGUAGES = [
        "python", "javascript", "typescript", "java", "go", "rust",
        "ruby", "php", "c", "cpp", "csharp", "swift", "kotlin"
    ]
    
    # Common topics for finding active repos
    TOPICS = [
        "web", "api", "cli", "tool", "library", "framework",
        "machine-learning", "data-science", "game", "mobile"
    ]
    
    def __init__(self, token: Optional[str] = None):
        """Initialize discovery with optional GitHub token for higher rate limits."""
        self.token = token
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"token {token}"
    
    async def search_repos(
        self,
        language: Optional[str] = None,
        topic: Optional[str] = None,
        min_stars: int = 10,
        max_results: int = 30
    ) -> List[dict]:
        """Search for repositories on GitHub.
        
        Args:
            language: Filter by programming language
            topic: Filter by topic
            min_stars: Minimum star count
            max_results: Maximum number of repos to return
        
        Returns:
            List of repo dicts with owner and name
        """
        query_parts = [f"stars:>={min_stars}"]
        
        if language:
            query_parts.append(f"language:{language}")
        if topic:
            query_parts.append(f"topic:{topic}")
        
        # Add random sort to get different results each time
        query = " ".join(query_parts)
        
        url = "https://api.github.com/search/repositories"
        params = {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": min(max_results, 100)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
                
                repos = []
                for item in data.get("items", [])[:max_results]:
                    repos.append({
                        "owner": item["owner"]["login"],
                        "name": item["name"],
                        "full_name": item["full_name"],
                        "stars": item["stargazers_count"],
                    })
                
                return repos
            except Exception as e:
                print(f"Error searching repos: {e}")
                return []
    
    async def get_recent_commits(
        self,
        owner: str,
        repo: str,
        max_commits: int = 30
    ) -> List[str]:
        """Get recent commit SHAs from a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            max_commits: Maximum number of commits to fetch
        
        Returns:
            List of commit SHAs
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"per_page": min(max_commits, 100)}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers)
                resp.raise_for_status()
                commits = resp.json()
                
                return [commit["sha"] for commit in commits]
            except Exception as e:
                print(f"Error fetching commits from {owner}/{repo}: {e}")
                return []
    
    def generate_patch_url(self, owner: str, repo: str, commit_sha: str) -> str:
        """Generate a .patch URL for a commit.
        
        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA
        
        Returns:
            URL to the .patch file
        """
        return f"https://github.com/{owner}/{repo}/commit/{commit_sha}.patch"
    
    async def discover_random_patches(
        self,
        count: int = 10,
        language: Optional[str] = None,
        topic: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Discover random commit .patch URLs.
        
        Args:
            count: Number of patch URLs to generate
            language: Filter repos by language (or random if None)
            topic: Filter repos by topic (or random if None)
        
        Yields:
            .patch URLs
        """
        # Use random language/topic if not specified
        if not language:
            language = random.choice(self.LANGUAGES)
        if not topic:
            topic = random.choice(self.TOPICS)
        
        print(f"🔍 Searching repos: language={language}, topic={topic}")
        
        # Find repos
        repos = await self.search_repos(
            language=language,
            topic=topic,
            min_stars=10,
            max_results=10
        )
        
        if not repos:
            print(f"⚠️  No repos found with language={language}, topic={topic}")
            return
        
        print(f"✓ Found {len(repos)} repositories")
        
        # Shuffle repos for randomness
        random.shuffle(repos)
        
        patches_yielded = 0
        
        for repo in repos:
            if patches_yielded >= count:
                break
            
            # Get recent commits from this repo
            commits = await self.get_recent_commits(
                repo["owner"],
                repo["name"],
                max_commits=10
            )
            
            if not commits:
                continue
            
            # Randomly select some commits
            selected = random.sample(commits, min(len(commits), count - patches_yielded))
            
            for commit_sha in selected:
                if patches_yielded >= count:
                    break
                
                patch_url = self.generate_patch_url(
                    repo["owner"],
                    repo["name"],
                    commit_sha
                )
                
                patches_yielded += 1
                yield patch_url
            
            # Rate limiting - small delay between repos
            await asyncio.sleep(0.5)
    
    async def discover_from_popular_repos(
        self,
        count: int = 10,
        repos: Optional[List[str]] = None
    ) -> AsyncGenerator[str, None]:
        """Discover commits from a list of popular repositories.
        
        Args:
            count: Number of patch URLs to generate
            repos: List of repo names in "owner/repo" format
        
        Yields:
            .patch URLs
        """
        if not repos:
            # Default popular repos
            repos = [
                "torvalds/linux",
                "python/cpython",
                "nodejs/node",
                "golang/go",
                "rust-lang/rust",
                "microsoft/vscode",
                "facebook/react",
                "vuejs/vue",
                "tensorflow/tensorflow",
                "django/django",
            ]
        
        random.shuffle(repos)
        patches_yielded = 0
        
        for repo_name in repos:
            if patches_yielded >= count:
                break
            
            try:
                owner, name = repo_name.split("/")
            except ValueError:
                print(f"⚠️  Invalid repo format: {repo_name}")
                continue
            
            commits = await self.get_recent_commits(owner, name, max_commits=20)
            
            if not commits:
                continue
            
            selected = random.sample(commits, min(len(commits), count - patches_yielded))
            
            for commit_sha in selected:
                if patches_yielded >= count:
                    break
                
                patch_url = self.generate_patch_url(owner, name, commit_sha)
                patches_yielded += 1
                yield patch_url
            
            await asyncio.sleep(0.5)
