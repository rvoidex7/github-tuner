import asyncio
import json
import logging
import os
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RawFinding:
    title: str
    url: str
    description: str
    stars: int
    language: str
    readme_content: str

class Hunter:
    def __init__(self, strategy_path: str = "strategy.json"):
        self.strategy_path = strategy_path
        self.client = httpx.AsyncClient(headers={"User-Agent": "GitHub-Tuner/1.0"}, follow_redirects=True)

    async def close(self):
        await self.client.aclose()

    def _load_strategy(self) -> Dict[str, Any]:
        """Load the search strategy."""
        try:
            with open(self.strategy_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Strategy file {self.strategy_path} not found. Using default.")
            return {
                "keywords": ["machine learning", "python"],
                "min_stars": 100,
                "languages": ["Python"]
            }

    async def search_github(self) -> List[RawFinding]:
        """Search GitHub based on strategy."""
        strategy = self._load_strategy()
        keywords = strategy.get("keywords", [])
        languages = strategy.get("languages", [])
        min_stars = strategy.get("min_stars", 50)

        query_parts = keywords.copy()
        for lang in languages:
            query_parts.append(f"language:{lang}")
        query_parts.append(f"stars:>={min_stars}")

        query = " ".join(query_parts)
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=10"

        logger.info(f"Searching GitHub: {query}")

        try:
            # Check for token
            headers = {}
            token = os.getenv("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"token {token}"

            resp = await self.client.get(url, headers=headers)

            if resp.status_code == 403:
                logger.warning("Rate limited by GitHub API. Returning mock data if allowed.")
                return []

            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])
            tasks = []

            # Create tasks for concurrent fetching
            for item in items:
                tasks.append(self._process_item(item))

            # Gather results
            findings = await asyncio.gather(*tasks)
            return findings

        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return []

    async def _process_item(self, item: Dict[str, Any]) -> RawFinding:
        """Fetch readme and create RawFinding object."""
        readme = await self._fetch_readme(item["owner"]["login"], item["name"], item["default_branch"])
        return RawFinding(
            title=item["full_name"],
            url=item["html_url"],
            description=item["description"] or "",
            stars=item["stargazers_count"],
            language=item["language"] or "Unknown",
            readme_content=readme
        )

    async def _fetch_readme(self, owner: str, repo: str, branch: str) -> str:
        """Fetch README raw content."""
        # Try common README filenames
        filenames = ["README.md", "readme.md", "README.rst", "README.txt"]

        for fname in filenames:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{fname}"
            try:
                resp = await self.client.get(url)
                if resp.status_code == 200:
                    return resp.text
            except Exception:
                continue

        return ""
