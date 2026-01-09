import asyncio
import json
import logging
import os
import httpx
from typing import List, Dict, Any, Optional, Tuple
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

    async def search_raw(self, query: str, page: int = 1, per_page: int = 10) -> Tuple[List[Dict[str, Any]], Dict[str, str], int]:
        """
        Execute a raw GitHub search.
        Returns: (items, response_headers, total_count)
        """
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page={per_page}&page={page}"
        logger.debug(f"Executing search: {url}")

        try:
            headers = {}
            token = os.getenv("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"token {token}"

            resp = await self.client.get(url, headers=headers)
            data = resp.json()

            # We return headers so the RateLimitMonitor can track them
            return data.get("items", []), dict(resp.headers), data.get("total_count", 0)

        except Exception as e:
            logger.error(f"GitHub raw search failed: {e}")
            return [], {}, 0

    async def search_github(self) -> List[RawFinding]:
        """Legacy synchronous-style search (for CLI compatibility)."""
        logger.warning("Using legacy search_github. Switching to workers recommended.")

        strategy = self._load_strategy()
        keywords = strategy.get("keywords", [])
        languages = strategy.get("languages", [])
        min_stars = strategy.get("min_stars", 50)

        query_parts = keywords.copy()
        for lang in languages:
            query_parts.append(f"language:{lang}")
        query_parts.append(f"stars:>={min_stars}")
        query = " ".join(query_parts)

        # Simple random page
        import random
        page = random.randint(1, 5)

        # Simple sleep to be nice to API in legacy mode
        import asyncio
        await asyncio.sleep(1)

        items, _, _ = await self.search_raw(query, page=page)

        findings = []
        for item in items:
            findings.append(await self._process_item(item))

        return findings

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

    async def fetch_user_starred_repos(self, limit: int = 100) -> List[str]:
        """Fetches descriptions of repos starred by the authenticated user."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            logger.warning("No GITHUB_TOKEN found. Cannot fetch user stars.")
            return []

        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = "https://api.github.com/user/starred"

        descriptions = []
        page = 1

        try:
            while len(descriptions) < limit:
                # Always fetch 100 per page to maintain consistent pagination offsets
                params = {
                    "per_page": 100,
                    "sort": "created",
                    "direction": "desc",
                    "page": page
                }

                resp = await self.client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                repos = resp.json()

                if not repos:
                    break

                for repo in repos:
                    if len(descriptions) >= limit:
                        break

                    desc = repo.get("description") or ""
                    title = repo.get("full_name") or ""
                    # Combine title and description for better context
                    text = f"{title} {desc}".strip()
                    if text:
                        descriptions.append(text)

                if len(repos) < 100:
                    break

                page += 1

            return descriptions

        except Exception as e:
            logger.error(f"Failed to fetch user stars: {e}")
            return descriptions

    async def star_repo(self, owner: str, repo: str) -> bool:
        """Stars a repo on GitHub via API (PUT /user/starred/{owner}/{repo})."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            logger.warning("No GITHUB_TOKEN found. Cannot star repo.")
            return False

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Length": "0"
        }
        url = f"https://api.github.com/user/starred/{owner}/{repo}"

        try:
            resp = await self.client.put(url, headers=headers)
            if resp.status_code == 204:
                logger.info(f"Successfully starred {owner}/{repo}")
                return True
            else:
                logger.error(f"Failed to star {owner}/{repo}: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Exception starring repo {owner}/{repo}: {e}")
            return False
