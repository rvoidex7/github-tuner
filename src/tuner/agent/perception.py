import feedparser
import requests
from fake_useragent import UserAgent
from playwright.async_api import async_playwright
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class RSSReader:
    def fetch_feed(self, url: str) -> List[Dict[str, Any]]:
        ua = UserAgent()
        headers = {
            'User-Agent': ua.random,
            'Accept': 'application/rss+xml, application/xml, text/xml',
            'Referer': 'https://www.google.com/'
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"Feed parse warning for {url}: {feed.bozo_exception}")

            entries = []
            for entry in feed.entries:
                entries.append({
                    "title": entry.get("title"),
                    "link": entry.get("link"),
                    "summary": entry.get("summary", "")[:500],
                    "published": entry.get("published")
                })
            return entries
        except Exception as e:
            logger.error(f"Error fetching RSS {url}: {e}")
            return []

class WebScraper:
    async def scrape_page(self, url: str) -> Dict[str, Any]:
        """Scrape a webpage using stealth Playwright."""
        ua = UserAgent()
        user_agent_str = ua.random

        async with async_playwright() as p:
            # Stealth args
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )

            context = await browser.new_context(
                user_agent=user_agent_str,
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                java_script_enabled=True
            )

            # Stealth scripts: Mask webdriver property
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = await context.new_page()

            try:
                # Wait for network idle to ensure SPA loads
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Human-like interaction: Scroll a bit
                await page.mouse.move(100, 100)
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(1)

                title = await page.title()
                # Get main text content
                text = await page.inner_text("body")

                return {
                    "url": url,
                    "title": title,
                    "content": text[:5000] # Limit content for token economy
                }
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return {"error": str(e)}
            finally:
                await browser.close()
