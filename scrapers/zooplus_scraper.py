"""Zooplus.de competitor discovery scraper for the German pet supplements market."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import SOURCE_ZOOPLUS_ENABLED, ZOOPLUS_BASE_URL
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# German-language search terms for common supplement categories
GERMAN_SUPPLEMENT_KEYWORDS: list[str] = [
    "Nahrungsergänzung",
    "Ergänzungsfuttermittel",
    "Gelenk",
    "Haut Fell",
    "Verdauung",
    "Beruhigung",
    "Immunsystem",
    "Vitamine",
    "Omega",
    "Probiotika",
]


class ZooplusScraper(BaseScraper):
    """Scraper for zooplus.de — searches for pet nutraceutical supplements
    on the German market.

    Follows the same patterns as ``ChewyScraper``: paginated search,
    card-based result parsing, and optional detail-page scraping.
    """

    def __init__(self) -> None:
        super().__init__(
            base_url=ZOOPLUS_BASE_URL,
            source_name="zooplus",
            enabled=SOURCE_ZOOPLUS_ENABLED,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search_products(
        self,
        search_term: str,
        max_pages: int = 3,
    ) -> list[dict]:
        """Search Zooplus for products matching *search_term*.

        Returns a list of raw product dicts parsed from search result pages.
        """
        products: list[dict] = []
        encoded_term = quote_plus(search_term)

        for page in range(1, max_pages + 1):
            url = f"{self.base_url}suche?q={encoded_term}&p={page}"

            if not self.is_allowed(url):
                logger.warning("Search URL disallowed by robots.txt: %s", url)
                break

            html = self.fetch(url)
            if not html:
                logger.warning(
                    "Failed to fetch search page %d for '%s'", page, search_term
                )
                break

            soup = BeautifulSoup(html, "lxml")
            page_products = self._parse_search_results(soup, url, search_term)

            if not page_products:
                logger.info(
                    "No more results on page %d for '%s'", page, search_term
                )
                break

            products.extend(page_products)
            logger.info(
                "Found %d products on page %d for '%s'",
                len(page_products),
                page,
                search_term,
            )

        return products

    # ------------------------------------------------------------------
    # Parse search results
    # ------------------------------------------------------------------
    def _parse_search_results(
        self,
        soup: BeautifulSoup,
        base_url: str,
        search_term: str,
    ) -> list[dict]:
        """Parse product cards from a Zooplus search results page."""
        products: list[dict] = []

        # Try multiple selectors for product cards
        card_selectors = [
            "[data-testid='product-card']",
            ".product-card",
            ".ProductCard",
            "article[class*='product']",
            "[class*='productCard']",
            ".product-list__item",
        ]

        cards = []
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                break

        # Fallback: JSON-LD structured data
        if not cards:
            products.extend(self._parse_from_json_ld(soup, search_term))
            if products:
                return products
            cards = soup.select(
                "section article, .results article, [class*='Card']"
            )

        for rank, card in enumerate(cards, 1):
            try:
                product = self._parse_product_card(card, base_url, search_term, rank)
                if product:
                    products.append(product)
            except Exception as exc:
                logger.warning("Failed to parse Zooplus product card: %s", exc)

        return products

    def _parse_from_json_ld(
        self, soup: BeautifulSoup, search_term: str
    ) -> list[dict]:
        """Try to extract products from JSON-LD structured data."""
        products: list[dict] = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            products.append(
                                self._json_ld_to_product(item, search_term)
                            )
                elif isinstance(data, dict):
                    if data.get("@type") == "Product":
                        products.append(
                            self._json_ld_to_product(data, search_term)
                        )
                    elif data.get("@type") == "ItemList":
                        for i, item in enumerate(
                            data.get("itemListElement", []), 1
                        ):
                            if (
                                "item" in item
                                and item["item"].get("@type") == "Product"
                            ):
                                p = self._json_ld_to_product(
                                    item["item"], search_term
                                )
                                p["marketplace_rank_position"] = i
                                products.append(p)
            except (json.JSONDecodeError, TypeError):
                continue
        return products

    def _json_ld_to_product(self, data: dict, search_term: str) -> dict:
        offers = data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_str = offers.get("price")
        return {
            "source": "zooplus",
            "search_term": search_term,
            "brand": (
                data.get("brand", {}).get("name", "")
                if isinstance(data.get("brand"), dict)
                else str(data.get("brand", ""))
            ),
            "product_name": data.get("name", ""),
            "product_url": data.get("url", ""),
            "rating": (
                float(data["aggregateRating"]["ratingValue"])
                if "aggregateRating" in data
                else None
            ),
            "review_count": (
                int(data["aggregateRating"]["reviewCount"])
                if "aggregateRating" in data
                else None
            ),
            "price": float(price_str) if price_str else None,
            "currency": offers.get("priceCurrency", "EUR"),
            "availability": offers.get("availability", ""),
            "image_url": data.get("image", ""),
            "raw_metadata": json.dumps(data),
        }

    # ------------------------------------------------------------------
    # Parse a single product card
    # ------------------------------------------------------------------
    def _parse_product_card(
        self,
        card,
        base_url: str,
        search_term: str,
        rank: int,
    ) -> dict | None:
        """Parse a single product card element from Zooplus search results."""
        link = card.select_one("a[href]")
        if not link:
            return None

        product_name = link.get_text(strip=True)
        product_url = urljoin(base_url, link["href"])

        if not product_name:
            title_el = card.select_one(
                "h2, h3, [class*='title'], [class*='name']"
            )
            product_name = title_el.get_text(strip=True) if title_el else ""

        if not product_name:
            return None

        # Brand
        brand_el = card.select_one("[class*='brand'], [class*='Brand']")
        brand = brand_el.get_text(strip=True) if brand_el else ""

        # Price (EUR format: 12,99 € or €12.99)
        price: float | None = None
        currency = "EUR"
        price_el = card.select_one("[class*='price'], [class*='Price']")
        if price_el:
            price_text = price_el.get_text(strip=True)
            price_match = re.search(r"(\d+[.,]\d{2})", price_text)
            if price_match:
                price = float(price_match.group(1).replace(",", "."))

        # Rating
        rating: float | None = None
        rating_el = card.select_one(
            "[class*='rating'], [class*='Rating'], [class*='star']"
        )
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            rating_match = re.search(r"(\d+[.,]?\d*)", rating_text)
            if rating_match:
                rating = float(rating_match.group(1).replace(",", "."))

        # Review count
        review_count: int | None = None
        review_el = card.select_one("[class*='review'], [class*='Review']")
        if review_el:
            review_text = review_el.get_text(strip=True)
            review_match = re.search(r"(\d[\d.]*)", review_text)
            if review_match:
                review_count = int(
                    review_match.group(1).replace(".", "")
                )

        # Image
        img = card.select_one("img")
        image_url = (img.get("src") or img.get("data-src")) if img else None

        # Pack size
        pack_size: str | None = None
        size_match = re.search(
            r"(\d+\s*(?:g|kg|ml|l|Stück|stk|Tabletten|Kapseln))",
            product_name,
            re.IGNORECASE,
        )
        if size_match:
            pack_size = size_match.group(1)

        return {
            "source": "zooplus",
            "search_term": search_term,
            "brand": brand,
            "product_name": product_name,
            "product_url": product_url,
            "marketplace_rank_position": rank,
            "rating": rating,
            "review_count": review_count,
            "price": price,
            "currency": currency,
            "pack_size": pack_size,
            "image_url": image_url,
            "availability": "in_stock",
            "raw_metadata": json.dumps(
                {"search_term": search_term, "rank": rank}
            ),
        }

    # ------------------------------------------------------------------
    # Full discovery
    # ------------------------------------------------------------------
    def discover_products(
        self,
        search_terms: list[dict[str, str]],
        max_pages_per_search: int = 2,
    ) -> list[dict]:
        """Run discovery across all search terms.

        Each item in *search_terms* should have keys:
        ``search_term``, ``animal_type``, ``support_area``.
        """
        all_products: list[dict] = []
        seen_urls: set[str] = set()

        for i, term_info in enumerate(search_terms, 1):
            search_term = term_info["search_term"]
            logger.info(
                "Zooplus search %d/%d: '%s'",
                i,
                len(search_terms),
                search_term,
            )

            results = self.search_products(
                search_term, max_pages=max_pages_per_search
            )

            for product in results:
                url = product.get("product_url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                product["_search_animal_type"] = term_info.get(
                    "animal_type", "unknown"
                )
                product["_search_support_area"] = term_info.get(
                    "support_area", "unknown"
                )
                all_products.append(product)

        logger.info(
            "Discovered %d unique products from Zooplus", len(all_products)
        )
        return all_products
