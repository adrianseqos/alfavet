"""Taxonomy classifier: maps raw product data to standardized support areas and animal types."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from taxonomy.support_areas import (
    ANIMAL_TYPE_KEYWORDS,
    FORM_FACTORS,
    LIFE_STAGES,
    SUPPORT_AREA_TAXONOMY,
)


@dataclass
class ClassificationResult:
    support_areas: list[dict[str, object]] = field(default_factory=list)
    animal_types: list[str] = field(default_factory=list)
    life_stage: str | None = None
    form_factor: str | None = None


def _score_text(text: str, keywords: list[str]) -> tuple[float, str | None]:
    """Score how well text matches keyword list. Returns (score, evidence_snippet)."""
    text_lower = text.lower()
    hits = 0
    best_snippet: str | None = None
    for kw in keywords:
        if kw.lower() in text_lower:
            hits += 1
            idx = text_lower.index(kw.lower())
            start = max(0, idx - 30)
            end = min(len(text), idx + len(kw) + 30)
            best_snippet = text[start:end].strip()
    if not keywords:
        return 0.0, None
    return hits / len(keywords), best_snippet


def classify_support_areas(
    product_name: str,
    description: str = "",
    ingredients: str = "",
    claims: str = "",
) -> list[dict[str, object]]:
    """Classify product into support areas with confidence scores."""
    combined = f"{product_name} {description} {claims}".strip()
    results: list[dict[str, object]] = []

    for area_key, area_def in SUPPORT_AREA_TAXONOMY.items():
        if area_key in ("other", "unknown"):
            continue

        kw_score, kw_snippet = _score_text(combined, area_def["keywords"])
        ing_score, ing_snippet = _score_text(ingredients, area_def["ingredient_markers"])

        # Weighted combination: keywords 60%, ingredient markers 40%
        combined_score = kw_score * 0.6 + ing_score * 0.4

        if combined_score >= 0.08:  # Low threshold to catch relevant matches
            confidence = min(1.0, combined_score * 2.5)  # Scale up
            snippet = kw_snippet or ing_snippet or ""
            results.append({
                "support_area": area_key,
                "confidence_score": round(confidence, 2),
                "evidence_snippet": snippet,
            })

    results.sort(key=lambda x: x["confidence_score"], reverse=True)

    if not results:
        results.append({
            "support_area": "unknown",
            "confidence_score": 0.1,
            "evidence_snippet": "",
        })

    return results


def classify_animal_types(
    product_name: str,
    description: str = "",
    category: str = "",
) -> list[str]:
    """Classify product by target animal type(s)."""
    combined = f"{product_name} {description} {category}".lower()
    found: list[str] = []

    for animal, keywords in ANIMAL_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                if animal not in found:
                    found.append(animal)
                break

    if len(found) > 2:
        return ["multi-species"]
    if not found:
        return ["unknown"]
    return found


def classify_life_stage(
    product_name: str,
    description: str = "",
) -> str | None:
    """Detect life stage from product text."""
    combined = f"{product_name} {description}".lower()
    stage_keywords = {
        "puppy": ["puppy", "welpe", "welpen"],
        "kitten": ["kitten", "kätzchen"],
        "junior": ["junior", "young", "jung"],
        "senior": ["senior", "old", "alter", "ältere"],
        "adult": ["adult", "erwachsen"],
    }
    for stage, keywords in stage_keywords.items():
        for kw in keywords:
            if kw in combined:
                return stage
    return None


def classify_form_factor(
    product_name: str,
    description: str = "",
) -> str | None:
    """Detect dosage form factor."""
    combined = f"{product_name} {description}".lower()
    form_keywords = {
        "powder": ["powder", "pulver"],
        "tablet": ["tablet", "tablette"],
        "capsule": ["capsule", "kapsel"],
        "liquid": ["liquid", "flüssig", "lösung", "saft", "tropfen"],
        "paste": ["paste"],
        "gel": ["gel"],
        "chew": ["chew", "kautablette"],
        "treat": ["treat", "snack", "leckerli"],
        "spray": ["spray"],
        "oil": ["oil", "öl"],
        "granule": ["granulat", "granule"],
        "drop": ["drop", "tropfen"],
        "cream": ["cream", "creme", "salbe"],
        "ointment": ["ointment", "salbe"],
        "shampoo": ["shampoo"],
    }
    for form, keywords in form_keywords.items():
        for kw in keywords:
            if kw in combined:
                return form
    return None


def classify_product(
    product_name: str,
    description: str = "",
    ingredients: str = "",
    claims: str = "",
    category: str = "",
) -> ClassificationResult:
    """Full classification of a product."""
    return ClassificationResult(
        support_areas=classify_support_areas(product_name, description, ingredients, claims),
        animal_types=classify_animal_types(product_name, description, category),
        life_stage=classify_life_stage(product_name, description),
        form_factor=classify_form_factor(product_name, description),
    )
