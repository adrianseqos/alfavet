"""Normalization layer: cleans and standardizes scraped product data."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from taxonomy.classifier import classify_product


def normalize_text(text: str | None) -> str:
    """Basic text normalization."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_brand(brand: str | None) -> str:
    """Normalize brand name for deduplication."""
    if not brand:
        return ""
    return re.sub(r"[^a-z0-9]", "", brand.lower())


def normalize_product_name(name: str | None) -> str:
    """Normalize product name for deduplication."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"[®™©]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


def parse_ingredients(raw: str | None) -> list[dict[str, str]]:
    """Parse raw ingredients text into structured list."""
    if not raw:
        return []

    ingredients: list[dict[str, str]] = []

    # Split by common delimiters
    parts = re.split(r"[,;·•\n]", raw)
    for part in parts:
        part = part.strip()
        if not part or len(part) < 2:
            continue
        # Remove percentage/amount info for normalized version
        normalized = re.sub(r"\d+[.,]?\d*\s*(%|mg|g|iu|mcg|ml)", "", part, flags=re.I).strip()
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized:
            ingredients.append({
                "name": part,
                "normalized": normalized.lower(),
            })

    return ingredients


def normalize_alfavet_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw alfavet product dict for database storage."""
    description = raw.get("_description", "")
    body_text = raw.get("_body_text", "")
    ingredients_text = raw.get("_ingredients_text", "")
    claims = raw.get("claimed_benefits_raw", "")

    # Classify
    classification = classify_product(
        product_name=raw.get("product_name", ""),
        description=description,
        ingredients=ingredients_text,
        claims=claims,
        category=raw.get("category", ""),
    )

    # Parse ingredients
    ingredients = parse_ingredients(raw.get("active_ingredients_raw"))

    normalized = {
        "source_company": raw.get("source_company", "alfavet"),
        "source_site": raw.get("source_site", "alfavet.de"),
        "product_name": normalize_text(raw.get("product_name")),
        "brand": raw.get("brand") or "alfavet",
        "product_url": raw.get("product_url", ""),
        "category": normalize_text(raw.get("category")),
        "life_stage": classification.life_stage,
        "form_factor": classification.form_factor,
        "active_ingredients_raw": raw.get("active_ingredients_raw"),
        "ingredients_normalized": json.dumps(
            [i["normalized"] for i in ingredients]
        ) if ingredients else None,
        "claimed_benefits_raw": claims,
        "feeding_or_dosage_text": raw.get("feeding_or_dosage_text"),
        "pack_size": raw.get("pack_size"),
        "price": raw.get("price"),
        "currency": raw.get("currency"),
        "availability_status": raw.get("availability_status", "unknown"),
        "raw_payload": raw.get("raw_payload"),
    }

    # Attach classification results (used by persistence layer, not stored directly)
    normalized["_animal_types"] = classification.animal_types
    normalized["_support_areas"] = classification.support_areas
    normalized["_ingredients_parsed"] = ingredients
    normalized["_condition_raw"] = claims or description

    return normalized


def normalize_chewy_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw Chewy product dict for database storage."""
    product_name = raw.get("product_name", "")
    brand = raw.get("brand", "")
    search_term = raw.get("search_term", "")

    # Classify using product name + any available data
    classification = classify_product(
        product_name=product_name,
        description=search_term,
        ingredients=raw.get("active_ingredients_raw", ""),
        claims=raw.get("badges_claims_text", ""),
    )

    # Use search context as fallback for classification
    animal_types = classification.animal_types
    if animal_types == ["unknown"] and raw.get("_search_animal_type"):
        animal_types = [raw["_search_animal_type"]]

    support_areas = classification.support_areas
    if (
        len(support_areas) == 1
        and support_areas[0]["support_area"] == "unknown"
        and raw.get("_search_support_area")
    ):
        support_areas = [{
            "support_area": raw["_search_support_area"],
            "confidence_score": 0.5,
            "evidence_snippet": f"Matched via search term: {search_term}",
        }]

    normalized = {
        "source": "chewy",
        "search_term": search_term,
        "brand": brand,
        "product_name": normalize_text(product_name),
        "product_url": raw.get("product_url", ""),
        "marketplace_rank_position": raw.get("marketplace_rank_position"),
        "rating": raw.get("rating"),
        "review_count": raw.get("review_count"),
        "price": raw.get("price"),
        "currency": raw.get("currency", "USD"),
        "active_ingredients_raw": raw.get("active_ingredients_raw"),
        "pack_size": raw.get("pack_size"),
        "form_factor": classification.form_factor or raw.get("form_factor"),
        "badges_claims_text": raw.get("badges_claims_text"),
        "availability": raw.get("availability", "unknown"),
        "image_url": raw.get("image_url"),
        "raw_metadata": raw.get("raw_metadata"),
    }

    normalized["_animal_types"] = animal_types
    normalized["_support_areas"] = support_areas

    return normalized


def compute_dedup_key(
    brand: str,
    product_name: str,
    source: str,
    variant: str | None = None,
    url: str | None = None,
) -> str:
    """Compute a canonical deduplication key."""
    parts = [
        normalize_brand(brand),
        normalize_product_name(product_name),
        source.lower(),
    ]
    if variant:
        parts.append(variant.lower().strip())
    if url:
        parts.append(url.rstrip("/"))
    key_str = "|".join(parts)
    return hashlib.sha256(key_str.encode()).hexdigest()
