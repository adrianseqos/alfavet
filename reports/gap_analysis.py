"""Gap analysis engine: identifies portfolio coverage gaps."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.search_terms import SUPPORT_AREA_SYNONYMS
from db.crud import save_gap_snapshot
from db.models import (
    Product,
    ProductIngredient,
    ProductSpecies,
    ProductSupportArea,
)
from taxonomy.support_areas import ANIMAL_TYPES, FORM_FACTORS, LIFE_STAGES, SUPPORT_AREA_TAXONOMY

logger = logging.getLogger(__name__)


def _get_coverage_matrix(session: Session) -> dict[str, dict[str, int]]:
    """Build animal_type x support_area coverage matrix."""
    matrix: dict[str, dict[str, int]] = {}
    for animal in ANIMAL_TYPES:
        matrix[animal] = {}
        for area in SUPPORT_AREA_TAXONOMY:
            # Count products that have this animal AND this support area
            count = session.execute(
                select(func.count(Product.id))
                .join(ProductSpecies, Product.id == ProductSpecies.product_id)
                .join(ProductSupportArea, Product.id == ProductSupportArea.product_id)
                .where(
                    ProductSpecies.animal_type == animal,
                    ProductSupportArea.support_area == area,
                )
            ).scalar() or 0
            matrix[animal][area] = count
    return matrix


def _get_animal_type_counts(session: Session) -> dict[str, int]:
    """Count products per animal type."""
    result = session.execute(
        select(ProductSpecies.animal_type, func.count(ProductSpecies.product_id))
        .group_by(ProductSpecies.animal_type)
    ).all()
    return {row[0]: row[1] for row in result}


def _get_support_area_counts(session: Session) -> dict[str, int]:
    """Count products per support area."""
    result = session.execute(
        select(ProductSupportArea.support_area, func.count(ProductSupportArea.product_id))
        .group_by(ProductSupportArea.support_area)
    ).all()
    return {row[0]: row[1] for row in result}


def _get_life_stage_counts(session: Session) -> dict[str, int]:
    """Count products per life stage."""
    result = session.execute(
        select(Product.life_stage, func.count(Product.id))
        .where(Product.life_stage.isnot(None))
        .group_by(Product.life_stage)
    ).all()
    return {row[0]: row[1] for row in result}


def _get_form_factor_counts(session: Session) -> dict[str, int]:
    """Count products per form factor."""
    result = session.execute(
        select(Product.form_factor, func.count(Product.id))
        .where(Product.form_factor.isnot(None))
        .group_by(Product.form_factor)
    ).all()
    return {row[0]: row[1] for row in result}


def _get_ingredient_families(session: Session) -> dict[str, int]:
    """Count occurrences of each normalized ingredient."""
    result = session.execute(
        select(ProductIngredient.ingredient_normalized, func.count(ProductIngredient.id))
        .where(ProductIngredient.ingredient_normalized.isnot(None))
        .group_by(ProductIngredient.ingredient_normalized)
        .order_by(func.count(ProductIngredient.id).desc())
    ).all()
    return {row[0]: row[1] for row in result}


def generate_gap_keywords(animal_type: str | None, support_area: str | None) -> list[str]:
    """Generate search keywords for a given gap."""
    keywords = []
    synonyms = SUPPORT_AREA_SYNONYMS.get(support_area or "", [support_area or ""])

    animals = [animal_type] if animal_type else ["dog", "cat"]
    for animal in animals:
        for syn in synonyms:
            keywords.append(f"{animal} {syn} supplement")
    return keywords


def run_gap_analysis(session: Session, persist: bool = True) -> dict[str, Any]:
    """Run full gap analysis and return results.

    Returns a dict with:
    - coverage_matrix
    - animal_type_gaps
    - support_area_gaps
    - matrix_gaps (animal x support area)
    - life_stage_gaps
    - form_factor_gaps
    - ingredient_summary
    - prioritized_gap_list
    """
    logger.info("Running gap analysis...")

    # Build coverage data
    matrix = _get_coverage_matrix(session)
    animal_counts = _get_animal_type_counts(session)
    area_counts = _get_support_area_counts(session)
    life_stage_counts = _get_life_stage_counts(session)
    form_factor_counts = _get_form_factor_counts(session)
    ingredient_families = _get_ingredient_families(session)

    total_products = session.execute(
        select(func.count(Product.id))
    ).scalar() or 0

    # Identify gaps
    gaps: list[dict[str, Any]] = []

    # 1. Animal type gaps
    core_animals = ["dog", "cat", "horse"]
    for animal in ANIMAL_TYPES:
        if animal in ("unknown", "multi-species"):
            continue
        count = animal_counts.get(animal, 0)
        if count == 0:
            priority = "high" if animal in core_animals else "medium"
            gap = {
                "type": "animal_type",
                "dimension": animal,
                "product_count": 0,
                "priority": priority,
                "rationale": f"No products targeting {animal}. "
                + ("Core pet type with high market demand." if animal in core_animals
                   else "Niche animal type; moderate opportunity."),
                "search_keywords": generate_gap_keywords(animal, None),
            }
            gaps.append(gap)
            if persist:
                save_gap_snapshot(
                    session, "animal_type", animal,
                    has_coverage=False, product_count=0,
                    gap_priority=priority, rationale=gap["rationale"],
                    search_keywords=gap["search_keywords"],
                )

    # 2. Support area gaps
    common_areas = [
        "joint_mobility", "skin_coat", "digestion_gut",
        "calming_stress_behavior", "immune_support",
    ]
    for area in SUPPORT_AREA_TAXONOMY:
        if area in ("other", "unknown"):
            continue
        count = area_counts.get(area, 0)
        if count == 0:
            priority = "high" if area in common_areas else "medium"
            gap = {
                "type": "support_area",
                "dimension": area,
                "product_count": 0,
                "priority": priority,
                "rationale": f"No products in support area '{area}'. "
                + ("High-demand category in US/EU markets." if area in common_areas
                   else "Emerging or niche support area."),
                "search_keywords": generate_gap_keywords(None, area),
            }
            gaps.append(gap)
            if persist:
                save_gap_snapshot(
                    session, "support_area", area,
                    has_coverage=False, product_count=0,
                    gap_priority=priority, rationale=gap["rationale"],
                    search_keywords=gap["search_keywords"],
                )

    # 3. Matrix gaps (animal x support area)
    for animal in ["dog", "cat", "horse"]:
        for area in common_areas:
            count = matrix.get(animal, {}).get(area, 0)
            if count == 0:
                dim_key = f"{animal}__{area}"
                gap = {
                    "type": "matrix",
                    "dimension": dim_key,
                    "product_count": 0,
                    "priority": "high",
                    "rationale": (
                        f"No products for {animal} in '{area}'. "
                        f"This is a commonly addressed combination in competitor portfolios."
                    ),
                    "search_keywords": generate_gap_keywords(animal, area),
                }
                gaps.append(gap)
                if persist:
                    save_gap_snapshot(
                        session, "matrix", dim_key,
                        has_coverage=False, product_count=0,
                        gap_priority="high", rationale=gap["rationale"],
                        search_keywords=gap["search_keywords"],
                    )

    # 4. Life stage gaps
    expected_stages = ["puppy", "senior", "adult"]
    for stage in expected_stages:
        count = life_stage_counts.get(stage, 0)
        if count == 0:
            gap = {
                "type": "life_stage",
                "dimension": stage,
                "product_count": 0,
                "priority": "medium",
                "rationale": f"No products specifically targeting '{stage}' life stage.",
                "search_keywords": [f"{stage} dog supplement", f"{stage} cat supplement"],
            }
            gaps.append(gap)
            if persist:
                save_gap_snapshot(
                    session, "life_stage", stage,
                    has_coverage=False, product_count=0,
                    gap_priority="medium", rationale=gap["rationale"],
                    search_keywords=gap["search_keywords"],
                )

    # 5. Form factor gaps
    common_forms = ["powder", "tablet", "liquid", "chew", "paste"]
    for form in common_forms:
        count = form_factor_counts.get(form, 0)
        if count == 0:
            gap = {
                "type": "form_factor",
                "dimension": form,
                "product_count": 0,
                "priority": "low",
                "rationale": f"No products in '{form}' form factor. Could expand delivery options.",
                "search_keywords": [f"{form} dog supplement", f"{form} cat supplement"],
            }
            gaps.append(gap)
            if persist:
                save_gap_snapshot(
                    session, "form_factor", form,
                    has_coverage=False, product_count=0,
                    gap_priority="low", rationale=gap["rationale"],
                    search_keywords=gap["search_keywords"],
                )

    # Sort gaps by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: priority_order.get(g["priority"], 3))

    # Also persist covered areas
    if persist:
        for animal, count in animal_counts.items():
            if count > 0:
                save_gap_snapshot(
                    session, "animal_type", animal,
                    has_coverage=True, product_count=count,
                )
        for area, count in area_counts.items():
            if count > 0:
                save_gap_snapshot(
                    session, "support_area", area,
                    has_coverage=True, product_count=count,
                )

    result = {
        "total_products": total_products,
        "coverage_matrix": matrix,
        "animal_type_counts": animal_counts,
        "support_area_counts": area_counts,
        "life_stage_counts": life_stage_counts,
        "form_factor_counts": form_factor_counts,
        "ingredient_families": dict(list(ingredient_families.items())[:30]),
        "prioritized_gap_list": gaps,
        "gap_count": len(gaps),
    }

    logger.info(
        "Gap analysis complete: %d total products, %d gaps identified",
        total_products, len(gaps),
    )
    return result
