"""Alfavet product scraper — one-time portfolio extraction."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config.settings import ALFAVET_BASE_URL, SOURCE_ALFAVET_ENABLED
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AlfavetScraper(BaseScraper):
    """Scraper for alfavet.de product portfolio."""

    def __init__(self):
        super().__init__(
            base_url=ALFAVET_BASE_URL,
            source_name="alfavet",
            enabled=SOURCE_ALFAVET_ENABLED,
        )

    def discover_product_urls(self) -> list[str]:
        """Discover all product page URLs from the site."""
        product_urls: list[str] = []

        # Try common product listing patterns
        listing_paths = [
            "/produkte/",
            "/products/",
            "/shop/",
            "/",
        ]

        visited_listings: set[str] = set()

        for path in listing_paths:
            url = self.absolute_url(path)
            if url in visited_listings:
                continue
            visited_listings.add(url)

            html = self.fetch(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            urls_from_page = self._extract_product_links(soup, url)
            product_urls.extend(urls_from_page)

            # Follow pagination
            page = 1
            while True:
                page += 1
                next_urls = self._find_next_page(soup, url, page)
                if not next_urls:
                    break
                next_html = self.fetch(next_urls)
                if not next_html:
                    break
                soup = BeautifulSoup(next_html, "lxml")
                new_links = self._extract_product_links(soup, next_urls)
                if not new_links:
                    break
                product_urls.extend(new_links)

        # Also try sitemap
        sitemap_urls = self._discover_from_sitemap()
        product_urls.extend(sitemap_urls)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_urls: list[str] = []
        for u in product_urls:
            normalized = u.rstrip("/")
            if normalized not in seen:
                seen.add(normalized)
                unique_urls.append(u)

        logger.info("Discovered %d unique product URLs from alfavet.de", len(unique_urls))
        return unique_urls

    def _discover_from_sitemap(self) -> list[str]:
        """Try to discover product URLs from sitemap.xml."""
        urls: list[str] = []
        sitemap_url = self.absolute_url("/sitemap.xml")
        html = self.fetch(sitemap_url)
        if not html:
            return urls

        soup = BeautifulSoup(html, "lxml")

        # Check for sitemap index
        sitemaps = soup.find_all("sitemap")
        if sitemaps:
            for sm in sitemaps:
                loc = sm.find("loc")
                if loc:
                    sub_html = self.fetch(loc.text.strip())
                    if sub_html:
                        sub_soup = BeautifulSoup(sub_html, "lxml")
                        urls.extend(self._extract_urls_from_sitemap(sub_soup))
        else:
            urls.extend(self._extract_urls_from_sitemap(soup))

        # Filter for product-like URLs
        product_urls = [
            u for u in urls
            if any(kw in u.lower() for kw in [
                "/produkt", "/product", "/shop/", "ergaenz", "supplement",
                "pflege", "care", "futter",
            ])
        ]

        logger.info("Found %d product URLs from sitemap", len(product_urls))
        return product_urls if product_urls else urls

    def _extract_urls_from_sitemap(self, soup: BeautifulSoup) -> list[str]:
        urls = []
        for loc in soup.find_all("loc"):
            url_text = loc.text.strip()
            if url_text:
                urls.append(url_text)
        return urls

    def _extract_product_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract product links from a listing page."""
        links: list[str] = []

        # Look for product links in common patterns
        selectors = [
            "a.product-link",
            "a.product-item-link",
            ".product a",
            ".products a",
            ".product-list a",
            "article a",
            ".card a",
            ".item a",
            "a[href*='produkt']",
            "a[href*='product']",
        ]

        found_links: set[str] = set()
        for selector in selectors:
            for a_tag in soup.select(selector):
                href = a_tag.get("href")
                if href:
                    full_url = urljoin(base_url, href)
                    if full_url not in found_links and self.base_url in full_url:
                        found_links.add(full_url)
                        links.append(full_url)

        # Also grab all internal links if specific selectors found nothing
        if not links:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                full_url = urljoin(base_url, href)
                if self.base_url in full_url and full_url not in found_links:
                    # Filter out obvious non-product pages
                    if not any(skip in full_url.lower() for skip in [
                        "/impressum", "/datenschutz", "/kontakt", "/agb",
                        "/warenkorb", "/cart", "/login", "/register",
                        "javascript:", "mailto:", "tel:", "#",
                        "/wp-content/", "/wp-admin/",
                    ]):
                        found_links.add(full_url)
                        links.append(full_url)

        return links

    def _find_next_page(self, soup: BeautifulSoup, current_url: str, page: int) -> str | None:
        """Find next pagination URL."""
        # Common pagination patterns
        for a_tag in soup.select("a.next, a.page-next, .pagination a"):
            href = a_tag.get("href")
            if href:
                return urljoin(current_url, href)

        # Try ?page=N pattern
        if "?" in current_url:
            base = current_url.split("?")[0]
        else:
            base = current_url
        return None  # Stop if no explicit next link

    def scrape_product_page(self, url: str) -> dict | None:
        """Scrape a single product page and extract structured data."""
        html = self.fetch(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        data: dict = {
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

        # Category / breadcrumb
        breadcrumb = soup.select_one(".breadcrumb, .breadcrumbs, [itemtype*='BreadcrumbList']")
        if breadcrumb:
            parts = [a.get_text(strip=True) for a in breadcrumb.find_all("a")]
            data["category"] = " > ".join(parts[1:]) if len(parts) > 1 else ""
        else:
            data["category"] = ""

        # Description
        desc_el = (
            soup.select_one(".product-description")
            or soup.select_one(".product-short-description")
            or soup.select_one("[itemprop='description']")
            or soup.select_one(".description")
        )
        description = desc_el.get_text(" ", strip=True) if desc_el else ""

        # Full body text for classification
        body_text = soup.get_text(" ", strip=True)

        # Price
        price_el = (
            soup.select_one(".price, [itemprop='price']")
            or soup.select_one(".product-price")
        )
        if price_el:
            price_text = price_el.get_text(strip=True)
            price_match = re.search(r"(\d+[.,]\d{2})", price_text)
            if price_match:
                data["price"] = float(price_match.group(1).replace(",", "."))
                data["currency"] = "EUR"
            else:
                data["price"] = None
                data["currency"] = None
        else:
            data["price"] = None
            data["currency"] = None

        # Availability
        avail_el = soup.select_one(".availability, .stock, [itemprop='availability']")
        data["availability_status"] = avail_el.get_text(strip=True) if avail_el else "unknown"

        # Ingredients
        ingredients_text = self._extract_section(soup, [
            "inhaltsstoffe", "zusammensetzung", "ingredients", "composition",
            "analytische bestandteile", "zusatzstoffe",
        ])
        data["active_ingredients_raw"] = ingredients_text

        # Claims / benefits
        claims_text = self._extract_section(soup, [
            "vorteile", "benefits", "wirkung", "anwendung", "eigenschaften",
            "besonderheiten", "highlights",
        ])
        data["claimed_benefits_raw"] = claims_text or description

        # Feeding / dosage
        dosage_text = self._extract_section(soup, [
            "fütterung", "dosierung", "feeding", "dosage", "anwendungshinweis",
            "fütterungsempfehlung",
        ])
        data["feeding_or_dosage_text"] = dosage_text

        # Pack size
        pack_el = soup.select_one(".pack-size, .weight, .product-weight")
        if pack_el:
            data["pack_size"] = pack_el.get_text(strip=True)
        else:
            # Try to find weight/size in product name or description
            size_match = re.search(
                r"(\d+\s*(?:g|kg|ml|l|tabletten|tabs|kapseln|stück))",
                f"{data['product_name']} {description}",
                re.IGNORECASE,
            )
            data["pack_size"] = size_match.group(1) if size_match else None

        # Store raw payload
        data["raw_payload"] = json.dumps({
            "description": description,
            "body_text_excerpt": body_text[:2000],
            "url": url,
        })

        # Store description and body text for classification (not DB fields)
        data["_description"] = description
        data["_body_text"] = body_text
        data["_ingredients_text"] = ingredients_text or ""

        if not data["product_name"]:
            logger.warning("No product name found at %s — skipping", url)
            return None

        return data

    def _extract_section(self, soup: BeautifulSoup, keywords: list[str]) -> str | None:
        """Extract text from a section identified by heading keywords."""
        for kw in keywords:
            # Try headings
            for heading in soup.find_all(["h2", "h3", "h4", "h5", "strong", "b", "dt"]):
                if kw.lower() in heading.get_text().lower():
                    # Get the next sibling content
                    content_parts = []
                    sibling = heading.find_next_sibling()
                    while sibling and sibling.name not in ["h2", "h3", "h4"]:
                        text = sibling.get_text(" ", strip=True)
                        if text:
                            content_parts.append(text)
                        sibling = sibling.find_next_sibling()
                    if content_parts:
                        return " ".join(content_parts)

            # Try tab panels or accordion items
            for el in soup.find_all(["div", "section"], class_=True):
                classes = " ".join(el.get("class", []))
                el_text = el.get_text(" ", strip=True)
                if kw.lower() in classes.lower() or (
                    kw.lower() in el_text[:100].lower() and len(el_text) > 20
                ):
                    return el_text

        return None

    def scrape_all(self) -> list[dict]:
        """Full portfolio scrape: discover URLs and scrape each product."""
        urls = self.discover_product_urls()
        products: list[dict] = []
        errors: list[str] = []

        for i, url in enumerate(urls, 1):
            logger.info("Scraping product %d/%d: %s", i, len(urls), url)
            try:
                product = self.scrape_product_page(url)
                if product:
                    products.append(product)
            except Exception as exc:
                logger.error("Failed to scrape %s: %s", url, exc)
                errors.append(f"{url}: {exc}")

        logger.info(
            "Scraped %d products from alfavet.de (%d errors)",
            len(products), len(errors),
        )
        return products
