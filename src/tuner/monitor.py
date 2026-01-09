import time
import asyncio
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class RateLimitMonitor:
    def __init__(self, safety_buffer: int = 5):
        self.remaining = 5000 # Default assumption
        self.reset_time = 0
        self.safety_buffer = safety_buffer
        self._lock = asyncio.Lock()

    def update_from_headers(self, headers: Dict[str, str]):
        """Update rate limit status from response headers."""
        try:
            # GitHub headers are case-insensitive usually, but httpx gives them lower-case or specific case
            # Standard GitHub: x-ratelimit-remaining, x-ratelimit-reset

            # Helper to find header case-insensitively
            def get_header(name):
                for k, v in headers.items():
                    if k.lower() == name.lower():
                        return v
                return None

            rem = get_header("x-ratelimit-remaining")
            res = get_header("x-ratelimit-reset")

            if rem is not None:
                self.remaining = int(rem)

            if res is not None:
                self.reset_time = int(res)

            # logger.debug(f"Rate Limit: {self.remaining} remaining, resets at {self.reset_time}")

        except Exception as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")

    async def check_and_sleep(self, task_name: str = "Worker"):
        """
        Check if we need to sleep based on rate limits.
        If remaining < safety_buffer, sleep until reset_time.
        """
        async with self._lock:
            if self.remaining < self.safety_buffer:
                now = int(time.time())
                wait_seconds = max(0, self.reset_time - now + 1)

                if wait_seconds > 0:
                    logger.warning(f"🛑 {task_name} hitting rate limit ({self.remaining} left). Sleeping for {wait_seconds}s...")
                    await asyncio.sleep(wait_seconds)

                    # Reset internal counter after sleep (optimistic)
                    # We assume it's reset, but next request will confirm
                    self.remaining = 5000
                    logger.info(f"🟢 {task_name} resuming...")
