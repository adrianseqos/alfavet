"""Playwright-based scraper for JavaScript-heavy pages.

Provides a PlaywrightScraper base class that renders JS before extracting content,
with configurable wait strategies, rate limiting, and retry logic.  Falls back
gracefully when the ``playwright`` package is not installed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any

from scrapers.base import BaseScraper
from config.settings import (
    SCRAPE_MAX_RETRIES,
    SCRAPE_RATE_LIMIT,
    SCRAPE_TIMEOUT,
    SCRAPE_USER_AGENT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful playwright import
# ---------------------------------------------------------------------------
try:
    from playwright.async_api import async_playwright, Browser, Page  # type: ignore[import-untyped]

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.info(
        "playwright is not installed — PlaywrightScraper will fall back to "
        "requests-based fetching.  Install with: pip install playwright && "
        "playwright install chromium"
    )


class WaitStrategy(str, Enum):
    """Supported Playwright wait strategies."""

    NETWORKIDLE = "networkidle"
    DOMCONTENTLOADED = "domcontentloaded"
    LOAD = "load"
    SELECTOR = "selector"


class PlaywrightScraper(BaseScraper):
    """Base scraper that uses Playwright to render JavaScript-heavy pages.

    Parameters
    ----------
    base_url:
        Root URL of the target site.
    source_name:
        Identifier for this source (used in logging / DB).
    enabled:
        Feature-flag; when ``False`` every fetch returns ``None``.
    wait_strategy:
        How to decide the page is "ready" — one of ``WaitStrategy`` values.
    wait_selector:
        CSS selector to wait for when ``wait_strategy`` is ``SELECTOR``.
    headless:
        Run the browser in headless mode (default ``True``).
    """

    def __init__(
        self,
        base_url: str,
        source_name: str,
        enabled: bool = True,
        wait_strategy: WaitStrategy = WaitStrategy.NETWORKIDLE,
        wait_selector: str | None = None,
        headless: bool = True,
    ) -> None:
        super().__init__(base_url=base_url, source_name=source_name, enabled=enabled)
        self.wait_strategy = wait_strategy
        self.wait_selector = wait_selector
        self.headless = headless
        self._browser: Browser | None = None
        self._pw_context: Any = None  # playwright context manager

    # ------------------------------------------------------------------
    # Async browser lifecycle
    # ------------------------------------------------------------------
    async def _ensure_browser(self) -> Browser:
        """Launch (or reuse) a Chromium browser instance."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "playwright is not installed.  "
                "Install with: pip install playwright && playwright install chromium"
            )
        if self._browser is None or not self._browser.is_connected():
            self._pw_context = await async_playwright().__aenter__()
            self._browser = await self._pw_context.chromium.launch(headless=self.headless)
            logger.info("Launched Chromium browser (headless=%s)", self.headless)
        return self._browser

    async def close(self) -> None:
        """Shut down the browser and Playwright context."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw_context is not None:
            await self._pw_context.__aexit__(None, None, None)
            self._pw_context = None

    # ------------------------------------------------------------------
    # Core async fetch
    # ------------------------------------------------------------------
    async def fetch_rendered(self, url: str) -> str | None:
        """Fetch *url*, render JavaScript, and return the resulting HTML.

        Uses the configured ``wait_strategy`` to decide when the page is
        ready.  Includes rate-limiting and exponential-backoff retry.

        Falls back to ``BaseScraper.fetch`` (requests) if Playwright is
        unavailable.
        """
        if not self.enabled:
            logger.info("Source %s is disabled, skipping %s", self.source_name, url)
            return None

        if not self.is_allowed(url):
            logger.warning("URL disallowed by robots.txt: %s", url)
            return None

        # Fallback when playwright is not installed
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(
                "Playwright unavailable — falling back to requests for %s", url
            )
            return self.fetch(url)

        for attempt in range(SCRAPE_MAX_RETRIES):
            self._rate_limit()
            page: Page | None = None
            try:
                browser = await self._ensure_browser()
                context = await browser.new_context(user_agent=SCRAPE_USER_AGENT)
                page = await context.new_page()

                # Navigate with chosen wait strategy
                if self.wait_strategy == WaitStrategy.SELECTOR and self.wait_selector:
                    await page.goto(url, timeout=SCRAPE_TIMEOUT * 1000)
                    await page.wait_for_selector(
                        self.wait_selector, timeout=SCRAPE_TIMEOUT * 1000
                    )
                else:
                    await page.goto(
                        url,
                        wait_until=self.wait_strategy.value,
                        timeout=SCRAPE_TIMEOUT * 1000,
                    )

                html = await page.content()
                logger.debug("Fetched rendered page %s (%d chars)", url, len(html))
                return html

            except Exception as exc:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Playwright fetch failed for %s (attempt %d/%d): %s — retrying in %ds",
                    url,
                    attempt + 1,
                    SCRAPE_MAX_RETRIES,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass

        logger.error("All retries exhausted for %s (playwright)", url)
        return None

    async def screenshot(self, url: str, path: str) -> bool:
        """Take a full-page screenshot and save it to *path*.

        Returns ``True`` on success, ``False`` on failure.
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright unavailable — cannot take screenshot of %s", url)
            return False

        if not self.enabled:
            return False

        page: Page | None = None
        try:
            browser = await self._ensure_browser()
            context = await browser.new_context(user_agent=SCRAPE_USER_AGENT)
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=SCRAPE_TIMEOUT * 1000)
            await page.screenshot(path=path, full_page=True)
            logger.info("Screenshot saved: %s -> %s", url, path)
            return True
        except Exception as exc:
            logger.error("Screenshot failed for %s: %s", url, exc)
            return False
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Alfavet-specific Playwright subclass
# ---------------------------------------------------------------------------
class PlaywrightAlfavetScraper(PlaywrightScraper):
    """Playwright-enabled scraper for alfavet.de.

    Useful when the alfavet site uses heavy client-side rendering that the
    standard requests-based ``AlfavetScraper`` cannot handle.
    """

    def __init__(self, enabled: bool = True) -> None:
        from config.settings import ALFAVET_BASE_URL, SOURCE_ALFAVET_ENABLED

        super().__init__(
            base_url=ALFAVET_BASE_URL,
            source_name="alfavet_pw",
            enabled=enabled and SOURCE_ALFAVET_ENABLED,
            wait_strategy=WaitStrategy.NETWORKIDLE,
            headless=True,
        )

    async def scrape_product_page(self, url: str) -> dict | None:
        """Render and extract structured data from a single product page.

        Returns a dict compatible with the ``AlfavetScraper`` output format,
        or ``None`` on failure.
        """
        import json
        import re

        from bs4 import BeautifulSoup

        html = await self.fetch_rendered(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        data: dict[str, Any] = {
            "source_company": "alfavet",
            "source_site": "alfavet.de",
            "product_url": url,
        }

        # Product name
        name_el = (
            soup.select_one("h1.product-title")
            or soup.select_one("h1.product_title")
            or soup.select_one("h1.entry-title")
            or soup.select_one("h1")
        )
        data["product_name"] = name_el.get_text(strip=True) if name_el else ""

        # Brand
        brand_el = soup.select_one(".brand, .product-brand, [itemprop='brand']")
        data["brand"] = brand_el.get_text(strip=True) if brand_el else "alfavet"

        # Description
        desc_el = (
            soup.select_one(".product-description")
            or soup.select_one("[itemprop='description']")
            or soup.select_one(".description")
        )
        data["_description"] = desc_el.get_text(" ", strip=True) if desc_el else ""
        data["_body_text"] = soup.get_text(" ", strip=True)

        # Price
        price_el = soup.select_one(".price, [itemprop='price']")
        if price_el:
            price_match = re.search(r"(\d+[.,]\d{2})", price_el.get_text(strip=True))
            if price_match:
                data["price"] = float(price_match.group(1).replace(",", "."))
                data["currency"] = "EUR"

        if not data["product_name"]:
            logger.warning("No product name found at %s — skipping", url)
            return None

        data["raw_payload"] = json.dumps({
            "description": data.get("_description", ""),
            "url": url,
        })
        return data
