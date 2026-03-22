"""Chewy.com competitor discovery scraper."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import CHEWY_BASE_URL, SOURCE_CHEWY_ENABLED
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ChewyScraper(BaseScraper):
    """Scraper for Chewy.com — searches for pet nutraceutical products."""

    def __init__(self):
        super().__init__(
            base_url=CHEWY_BASE_URL,
            source_name="chewy",
            enabled=SOURCE_CHEWY_ENABLED,
        )

    def search_products(
        self,
        search_term: str,
        max_pages: int = 3,
    ) -> list[dict]:
        """Search Chewy for products matching a search term.

        Returns a list of raw product dicts parsed from search results.
        """
        products: list[dict] = []
        encoded_term = quote_plus(search_term)

        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/s?query={encoded_term}&page={page}"

            if not self.is_allowed(url):
                logger.warning("Search URL disallowed by robots.txt: %s", url)
                break

            html = self.fetch(url)
            if not html:
                logger.warning("Failed to fetch search page %d for '%s'", page, search_term)
                break

            soup = BeautifulSoup(html, "lxml")
            page_products = self._parse_search_results(soup, url, search_term)

            if not page_products:
                logger.info("No more results on page %d for '%s'", page, search_term)
                break

            products.extend(page_products)
            logger.info(
                "Found %d products on page %d for '%s'",
                len(page_products), page, search_term,
            )

        return products

    def _parse_search_results(
        self,
        soup: BeautifulSoup,
        base_url: str,
        search_term: str,
    ) -> list[dict]:
        """Parse product cards from Chewy search results page."""
        products: list[dict] = []

        # Try multiple selectors for product cards
        card_selectors = [
            "[data-testid='product-card']",
            ".product-card",
            ".ProductCard",
            "article[class*='product']",
            ".kib-product-card",
            "[class*='productCard']",
        ]

        cards = []
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                break

        # Fallback: look for structured data
        if not cards:
            products.extend(self._parse_from_json_ld(soup, search_term))
            if products:
                return products

            # Try generic card patterns
            cards = soup.select("section article, .results article, [class*='Card']")

        for rank, card in enumerate(cards, 1):
            try:
                product = self._parse_product_card(card, base_url, search_term, rank)
                if product:
                    products.append(product)
            except Exception as exc:
                logger.warning("Failed to parse product card: %s", exc)

        return products

    def _parse_from_json_ld(self, soup: BeautifulSoup, search_term: str) -> list[dict]:
        """Try to extract product data from JSON-LD structured data."""
        products = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            products.append(self._json_ld_to_product(item, search_term))
                elif isinstance(data, dict):
                    if data.get("@type") == "Product":
                        products.append(self._json_ld_to_product(data, search_term))
                    elif data.get("@type") == "ItemList":
                        for i, item in enumerate(data.get("itemListElement", []), 1):
                            if "item" in item and item["item"].get("@type") == "Product":
                                p = self._json_ld_to_product(item["item"], search_term)
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
            "source": "chewy",
            "search_term": search_term,
            "brand": data.get("brand", {}).get("name", "") if isinstance(data.get("brand"), dict) else str(data.get("brand", "")),
            "product_name": data.get("name", ""),
            "product_url": data.get("url", ""),
            "rating": float(data["aggregateRating"]["ratingValue"]) if "aggregateRating" in data else None,
            "review_count": int(data["aggregateRating"]["reviewCount"]) if "aggregateRating" in data else None,
            "price": float(price_str) if price_str else None,
            "currency": offers.get("priceCurrency", "USD"),
            "availability": offers.get("availability", ""),
            "image_url": data.get("image", ""),
            "raw_metadata": json.dumps(data),
        }

    def _parse_product_card(
        self,
        card,
        base_url: str,
        search_term: str,
        rank: int,
    ) -> dict | None:
        """Parse a single product card element."""
        # Product name and URL
        link = card.select_one("a[href]")
        if not link:
            return None

        product_name = link.get_text(strip=True)
        product_url = urljoin(base_url, link["href"])

        if not product_name:
            title_el = card.select_one("h2, h3, [class*='title'], [class*='name']")
            product_name = title_el.get_text(strip=True) if title_el else ""

        if not product_name:
            return None

        # Brand
        brand_el = card.select_one("[class*='brand'], [class*='Brand']")
        brand = brand_el.get_text(strip=True) if brand_el else ""

        # Price
        price = None
        currency = "USD"
        price_el = card.select_one("[class*='price'], [class*='Price']")
        if price_el:
            price_text = price_el.get_text(strip=True)
            price_match = re.search(r"\$?(\d+\.?\d*)", price_text)
            if price_match:
                price = float(price_match.group(1))

        # Rating
        rating = None
        rating_el = card.select_one("[class*='rating'], [class*='Rating'], [class*='star']")
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            rating_match = re.search(r"(\d+\.?\d*)", rating_text)
            if rating_match:
                rating = float(rating_match.group(1))

        # Review count
        review_count = None
        review_el = card.select_one("[class*='review'], [class*='Review']")
        if review_el:
            review_text = review_el.get_text(strip=True)
            review_match = re.search(r"(\d[\d,]*)", review_text)
            if review_match:
                review_count = int(review_match.group(1).replace(",", ""))

        # Image
        img = card.select_one("img")
        image_url = img.get("src") or img.get("data-src") if img else None

        # Badges / claims
        badges = []
        for badge_el in card.select("[class*='badge'], [class*='Badge'], [class*='tag']"):
            badges.append(badge_el.get_text(strip=True))

        return {
            "source": "chewy",
            "search_term": search_term,
            "brand": brand,
            "product_name": product_name,
            "product_url": product_url,
            "marketplace_rank_position": rank,
            "rating": rating,
            "review_count": review_count,
            "price": price,
            "currency": currency,
            "badges_claims_text": "; ".join(badges) if badges else None,
            "image_url": image_url,
            "availability": "in_stock",
            "raw_metadata": json.dumps({"search_term": search_term, "rank": rank}),
        }

    def scrape_product_detail(self, url: str) -> dict | None:
        """Scrape additional details from a Chewy product page."""
        html = self.fetch(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        details: dict = {}

        # Ingredients
        for el in soup.find_all(["div", "section", "span"], string=re.compile(r"ingredient", re.I)):
            parent = el.find_parent(["div", "section"])
            if parent:
                details["active_ingredients_raw"] = parent.get_text(" ", strip=True)[:1000]
                break

        # Pack size / weight
        for el in soup.find_all(string=re.compile(r"\d+\s*(oz|lb|ct|count|pack)", re.I)):
            details["pack_size"] = el.strip()[:200]
            break

        # Form factor
        text = soup.get_text(" ", strip=True).lower()
        for form in ["chew", "tablet", "capsule", "powder", "liquid", "treat", "oil", "spray"]:
            if form in text:
                details["form_factor"] = form
                break

        return details

    def discover_products(
        self,
        search_terms: list[dict[str, str]],
        max_pages_per_search: int = 2,
        fetch_details: bool = False,
    ) -> list[dict]:
        """Run discovery across all search terms.

        Each item in search_terms should have: search_term, animal_type, support_area
        """
        all_products: list[dict] = []
        seen_urls: set[str] = set()

        for i, term_info in enumerate(search_terms, 1):
            search_term = term_info["search_term"]
            logger.info(
                "Search %d/%d: '%s'", i, len(search_terms), search_term
            )

            results = self.search_products(search_term, max_pages=max_pages_per_search)

            for product in results:
                url = product.get("product_url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Add classification context from search
                product["_search_animal_type"] = term_info.get("animal_type", "unknown")
                product["_search_support_area"] = term_info.get("support_area", "unknown")

                # Optionally fetch detail page
                if fetch_details and url:
                    details = self.scrape_product_detail(url)
                    if details:
                        product.update(details)

                all_products.append(product)

        logger.info("Discovered %d unique products from Chewy", len(all_products))
        return all_products
