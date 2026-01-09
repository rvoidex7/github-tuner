import asyncio
import logging
import json
import traceback
from typing import Dict, Any

from tuner.storage import TaskQueue, TunerStorage
from tuner.monitor import RateLimitMonitor
from tuner.hunter import Hunter
from tuner.brain import LocalBrain, CloudBrain

logger = logging.getLogger(__name__)

class WorkerManager:
    def __init__(self, db_path: str = "data/tuner.db"):
        self.queue = TaskQueue(db_path)
        self.storage = TunerStorage(db_path)
        self.monitor = RateLimitMonitor()

        # Shared resources
        self.local_brain = LocalBrain()
        self.cloud_brain = CloudBrain()

        # Hunter (API Client) - pass monitor
        # We need to refactor Hunter to accept monitor, or monkey-patch it,
        # or just let the worker handle the sleep and update monitor manually.
        # For now, we'll instantiate Hunter per use or shared.
        self.hunter = Hunter()
        # Ideally, Hunter should use a shared httpx client session, but it creates one in __init__.

        self.running = False

    async def start(self):
        self.running = True
        logger.info("👷 Workers started.")

        await self.storage.initialize()

        # Launch workers
        await asyncio.gather(
            self.scout_worker(),
            self.fetch_worker(),
            self.processor_worker(),
            self.processor_worker() # Multiple processors?
        )

    async def stop(self):
        self.running = False
        await self.hunter.close()

    async def scout_worker(self):
        """
        The Scout: Consumes 'search' tasks.
        Payload: { "query": "...", "page": 1, "min_stars": ... }
        """
        while self.running:
            try:
                task = await self.queue.pop_task("scout")
                if not task:
                    await asyncio.sleep(1) # Idle wait
                    continue

                logger.info(f"🔭 Scout picked up task: {task['id']}")
                payload = task['payload']

                # Check Rate Limit
                await self.monitor.check_and_sleep("Scout")

                # Execute Search
                # We need a method in Hunter that accepts raw query params and returns raw items
                # The current Hunter.search_github() is too high-level.
                # We will use Hunter's client directly or a new method.
                # Assuming we refactor Hunter to have `search_raw(query, page)`.

                # For now, let's assume payload has 'query'
                query = payload.get("query", "stars:>100")
                page = payload.get("page", 1)

                # Perform search (using a new method we'll add to Hunter)
                results, headers = await self.hunter.search_raw(query, page=page)

                # Update Monitor
                self.monitor.update_from_headers(headers)

                # Enqueue Results for Fetcher
                for item in results:
                    fetch_payload = {
                        "owner": item["owner"]["login"],
                        "repo": item["name"],
                        "branch": item["default_branch"],
                        "meta": item # Pass along metadata
                    }
                    await self.queue.enqueue_task("fetch_readme", fetch_payload, priority=5)

                logger.info(f"🔭 Scout found {len(results)} items.")
                await self.queue.complete_task(task['id'])

            except Exception as e:
                logger.error(f"Scout failed: {e}")
                # traceback.print_exc()
                if task:
                    await self.queue.fail_task(task['id'], str(e))
                await asyncio.sleep(5) # Backoff

    async def fetch_worker(self):
        """
        The Fetcher: Consumes 'fetch_readme' tasks.
        Payload: { "owner": "...", "repo": "...", "branch": "...", "meta": {...} }
        """
        while self.running:
            try:
                task = await self.queue.pop_task("fetcher")
                if not task:
                    await asyncio.sleep(0.5)
                    continue

                # logger.info(f"📥 Fetcher picked up task: {task['id']}")
                payload = task['payload']

                owner = payload["owner"]
                repo = payload["repo"]
                branch = payload["branch"]

                # Fetch Readme
                # Note: Raw content fetch doesn't usually consume Search API limit,
                # but might hit Core API limit if using API, or no limit if using raw.githubusercontent
                # Hunter uses raw.githubusercontent.

                readme_content = await self.hunter._fetch_readme(owner, repo, branch)

                if readme_content:
                    # Enqueue for Processor
                    analyze_payload = {
                        "meta": payload["meta"],
                        "readme": readme_content
                    }
                    await self.queue.enqueue_task("analyze", analyze_payload, priority=10)
                    # logger.info(f"📥 Fetched README for {owner}/{repo}")
                else:
                    logger.warning(f"Failed to fetch README for {owner}/{repo}")

                await self.queue.complete_task(task['id'])

            except Exception as e:
                logger.error(f"Fetcher failed: {e}")
                if task:
                    await self.queue.fail_task(task['id'], str(e))
                await asyncio.sleep(1)

    async def processor_worker(self):
        """
        The Processor: Consumes 'analyze' tasks.
        Payload: { "meta": {...}, "readme": "..." }
        """
        while self.running:
            try:
                task = await self.queue.pop_task("processor")
                if not task:
                    await asyncio.sleep(0.5)
                    continue

                payload = task['payload']
                meta = payload['meta']
                readme = payload['readme']

                # 1. Local Vectorization
                text = f"{meta['full_name']} {meta['description'] or ''}"
                # Ideally we want to vectorize the README too, but it might be too long.
                # Let's just use title+desc for now as per original logic, or add summary later.
                embedding = self.local_brain.vectorize(text)

                # Save initial finding
                f_id = await self.storage.save_finding(
                    title=meta['full_name'],
                    url=meta['html_url'],
                    description=meta['description'] or "",
                    stars=meta['stargazers_count'],
                    language=meta['language'] or "Unknown",
                    embedding=embedding.tobytes()
                )

                if f_id != -1:
                    # 2. Check if we should use Cloud Brain
                    # For now, let's just save it.
                    # The original logic filtered here.
                    # Let's assume the processor just ingests for now,
                    # OR we can do the screening here.

                    # NOTE: To keep it simple for this phase, we just save.
                    # Screening/Filtering can be a separate step or done here if we load user profile.
                    pass

                await self.queue.complete_task(task['id'])

            except Exception as e:
                logger.error(f"Processor failed: {e}")
                if task:
                    await self.queue.fail_task(task['id'], str(e))
                await asyncio.sleep(1)
