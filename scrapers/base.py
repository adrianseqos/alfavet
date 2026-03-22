"""Base scraper with rate limiting, retry logic, and robots.txt compliance."""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests

from config.settings import (
    SCRAPE_MAX_RETRIES,
    SCRAPE_RATE_LIMIT,
    SCRAPE_TIMEOUT,
    SCRAPE_USER_AGENT,
)

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base scraper with polite crawling, rate limiting, and retry."""

    def __init__(self, base_url: str, source_name: str, enabled: bool = True):
        self.base_url = base_url.rstrip("/")
        self.source_name = source_name
        self.enabled = enabled
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": SCRAPE_USER_AGENT})
        self._last_request_time: float = 0
        self._robots_parser: urllib.robotparser.RobotFileParser | None = None

    def _load_robots_txt(self) -> None:
        """Load and parse robots.txt."""
        try:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{self.base_url}/robots.txt"
            rp.set_url(robots_url)
            rp.read()
            self._robots_parser = rp
            logger.info("Loaded robots.txt from %s", robots_url)
        except Exception as exc:
            logger.warning("Could not load robots.txt for %s: %s", self.base_url, exc)
            self._robots_parser = None

    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        if self._robots_parser is None:
            self._load_robots_txt()
        if self._robots_parser is None:
            return True  # If we can't load robots.txt, proceed cautiously
        return self._robots_parser.can_fetch(SCRAPE_USER_AGENT, url)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < SCRAPE_RATE_LIMIT:
            time.sleep(SCRAPE_RATE_LIMIT - elapsed)
        self._last_request_time = time.time()

    def fetch(self, url: str) -> str | None:
        """Fetch a URL with rate limiting and retry logic."""
        if not self.enabled:
            logger.info("Source %s is disabled, skipping %s", self.source_name, url)
            return None

        if not self.is_allowed(url):
            logger.warning("URL disallowed by robots.txt: %s", url)
            return None

        for attempt in range(SCRAPE_MAX_RETRIES):
            self._rate_limit()
            try:
                resp = self._session.get(url, timeout=SCRAPE_TIMEOUT)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as exc:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Fetch failed for %s (attempt %d/%d): %s — retrying in %ds",
                    url, attempt + 1, SCRAPE_MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)

        logger.error("All retries exhausted for %s", url)
        return None

    def absolute_url(self, path: str) -> str:
        """Convert a relative path to an absolute URL."""
        return urljoin(self.base_url + "/", path)
