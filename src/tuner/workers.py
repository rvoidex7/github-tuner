import asyncio
import logging
import json
import traceback
from typing import Dict, Any

from tuner.storage import TaskQueue, TunerStorage
from tuner.monitor import RateLimitMonitor
from tuner.hunter import Hunter
from tuner.brain import LocalBrain, CloudBrain
from tuner.slicer import split_date_range, get_query_with_date

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
        The Scout: Consumes 'search' and 'discovery' tasks.
        """
        while self.running:
            try:
                task = await self.queue.pop_task("scout")
                if not task:
                    await asyncio.sleep(1) # Idle wait
                    continue

                # logger.info(f"🔭 Scout picked up task: {task['id']} ({task['type']})")
                payload = task['payload']

                # Check Rate Limit
                await self.monitor.check_and_sleep("Scout")

                if task['type'] == 'search':
                    await self._handle_search_task(task, payload)
                elif task['type'] == 'discovery':
                    await self._handle_discovery_task(task, payload)

                await self.queue.complete_task(task['id'])

            except Exception as e:
                logger.error(f"Scout failed: {e}")
                traceback.print_exc()
                if task:
                    await self.queue.fail_task(task['id'], str(e))
                await asyncio.sleep(5) # Backoff

    async def _handle_search_task(self, task, payload):
        """Handle standard paginated search task."""
        query = payload.get("query", "stars:>100")
        page = payload.get("page", 1)

        # Request 100 items per page to match discovery pagination logic
        results, headers, _ = await self.hunter.search_raw(query, page=page, per_page=100)
        self.monitor.update_from_headers(headers)

        for item in results:
            fetch_payload = {
                "owner": item["owner"]["login"],
                "repo": item["name"],
                "branch": item["default_branch"],
                "meta": item
            }
            await self.queue.enqueue_task("fetch_readme", fetch_payload, priority=5)

        logger.info(f"🔭 Scout (Page {page}) found {len(results)} items.")

    async def _handle_discovery_task(self, task, payload):
        """Handle recursive date slicing discovery."""
        base_query = payload.get("query")
        start_date = payload.get("start_date")
        end_date = payload.get("end_date")

        full_query = get_query_with_date(base_query, start_date, end_date)

        # Check count (Page 1)
        # We only need metadata here, but we get items too.
        results, headers, total_count = await self.hunter.search_raw(full_query, page=1, per_page=1)
        self.monitor.update_from_headers(headers)

        logger.info(f"🔭 Discovery [{start_date} .. {end_date}]: {total_count} repos found.")

        if total_count > 1000:
            # Split
            s, m, e = split_date_range(start_date, end_date)
            logger.info(f"✂️ Splitting: {s} -> {m} -> {e}")

            # Enqueue halves (High Priority to drill down fast)
            await self.queue.enqueue_task("discovery",
                {"query": base_query, "start_date": s, "end_date": m}, priority=task['priority'] + 1)
            await self.queue.enqueue_task("discovery",
                {"query": base_query, "start_date": m, "end_date": e}, priority=task['priority'] + 1)

        else:
            # Safe zone: Enqueue pages
            # GitHub max 1000 items, 100 per page = 10 pages.
            import math
            pages = min(10, math.ceil(total_count / 100.0))
            if pages == 0 and total_count > 0: pages = 1

            logger.info(f"✅ Safe Zone. Enqueuing {pages} page tasks.")

            for p in range(1, pages + 1):
                # Enqueue a standard search task for this specific range
                # We use the full_query which includes the date range
                await self.queue.enqueue_task("search",
                    {"query": full_query, "page": p}, priority=5)

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
