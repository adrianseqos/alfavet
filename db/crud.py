"""CRUD operations for the pet nutraceutical intelligence database."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    ChangeLog,
    CompetitorProduct,
    CompetitorProductSpecies,
    CompetitorProductSupportArea,
    GapAnalysisSnapshot,
    Product,
    ProductIngredient,
    ProductSpecies,
    ProductSupportArea,
    SourceRun,
)


def compute_content_hash(data: dict) -> str:
    """Canonical hash for deduplication."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Source runs
# ---------------------------------------------------------------------------
def create_source_run(session: Session, source: str, run_type: str) -> SourceRun:
    run = SourceRun(source=source, run_type=run_type)
    session.add(run)
    session.flush()
    return run


def finish_source_run(
    session: Session,
    run: SourceRun,
    status: str = "completed",
    products_found: int = 0,
    products_new: int = 0,
    products_updated: int = 0,
    error_message: str | None = None,
) -> None:
    run.finished_at = datetime.now(timezone.utc)
    run.status = status
    run.products_found = products_found
    run.products_new = products_new
    run.products_updated = products_updated
    run.error_message = error_message
    session.flush()


# ---------------------------------------------------------------------------
# Products (alfavet)
# ---------------------------------------------------------------------------
def upsert_product(session: Session, data: dict[str, Any]) -> tuple[Product, bool]:
    """Insert or update a product. Returns (product, is_new)."""
    existing = session.execute(
        select(Product).where(
            Product.source_company == data.get("source_company", "alfavet"),
            Product.product_url == data["product_url"],
        )
    ).scalar_one_or_none()

    content_hash = compute_content_hash({
        k: v for k, v in data.items()
        if k not in ("scraped_at", "raw_payload", "content_hash")
    })

    if existing:
        if existing.content_hash != content_hash:
            # Track changes
            for field in [
                "product_name", "brand", "category", "price", "currency",
                "availability_status", "pack_size", "active_ingredients_raw",
                "claimed_benefits_raw", "form_factor",
            ]:
                old_val = getattr(existing, field)
                new_val = data.get(field)
                if str(old_val) != str(new_val) and new_val is not None:
                    session.add(ChangeLog(
                        source=data.get("source_company", "alfavet"),
                        entity_type="product",
                        entity_id=existing.id,
                        field_name=field,
                        old_value=str(old_val) if old_val else None,
                        new_value=str(new_val),
                    ))

            for field, value in data.items():
                if field not in ("id", "species", "support_areas", "ingredients") and value is not None:
                    setattr(existing, field, value)
            existing.content_hash = content_hash
            existing.scraped_at = datetime.now(timezone.utc)
            session.flush()
        return existing, False

    product = Product(
        **{k: v for k, v in data.items()
           if k not in ("species", "support_areas", "ingredients")},
        content_hash=content_hash,
    )
    session.add(product)
    session.flush()
    return product, True


def set_product_species(session: Session, product_id: int, animal_types: list[str]) -> None:
    """Set species for a product (replaces existing)."""
    session.query(ProductSpecies).filter_by(product_id=product_id).delete()
    for at in animal_types:
        session.add(ProductSpecies(product_id=product_id, animal_type=at))
    session.flush()


def set_product_support_areas(
    session: Session,
    product_id: int,
    areas: list[dict[str, Any]],
    raw_condition: str | None = None,
) -> None:
    """Set support areas for a product."""
    session.query(ProductSupportArea).filter_by(product_id=product_id).delete()
    for area in areas:
        session.add(ProductSupportArea(
            product_id=product_id,
            support_area=area["support_area"],
            confidence_score=area.get("confidence_score"),
            evidence_snippet=area.get("evidence_snippet"),
            condition_or_support_area_raw=raw_condition,
        ))
    session.flush()


def set_product_ingredients(
    session: Session,
    product_id: int,
    ingredients: list[dict[str, str]],
) -> None:
    """Set ingredients for a product."""
    session.query(ProductIngredient).filter_by(product_id=product_id).delete()
    for ing in ingredients:
        session.add(ProductIngredient(
            product_id=product_id,
            ingredient_name=ing["name"],
            ingredient_normalized=ing.get("normalized"),
        ))
    session.flush()


# ---------------------------------------------------------------------------
# Competitor products
# ---------------------------------------------------------------------------
def upsert_competitor_product(
    session: Session,
    data: dict[str, Any],
    source_run_id: int | None = None,
) -> tuple[CompetitorProduct, bool]:
    """Insert or update a competitor product."""
    existing = session.execute(
        select(CompetitorProduct).where(
            CompetitorProduct.source == data["source"],
            CompetitorProduct.product_url == data["product_url"],
        )
    ).scalar_one_or_none()

    content_hash = compute_content_hash({
        k: v for k, v in data.items()
        if k not in ("discovered_at", "first_seen_at", "last_seen_at",
                      "is_new_this_run", "raw_metadata", "content_hash",
                      "source_run_id")
    })

    now = datetime.now(timezone.utc)

    if existing:
        is_changed = existing.content_hash != content_hash
        if is_changed:
            for field in ["price", "rating", "review_count", "availability",
                          "active_ingredients_raw", "badges_claims_text"]:
                old_val = getattr(existing, field)
                new_val = data.get(field)
                if str(old_val) != str(new_val) and new_val is not None:
                    session.add(ChangeLog(
                        source=data["source"],
                        entity_type="competitor_product",
                        entity_id=existing.id,
                        field_name=field,
                        old_value=str(old_val) if old_val else None,
                        new_value=str(new_val),
                        source_run_id=source_run_id,
                    ))

            for field, value in data.items():
                if field not in ("id", "species", "support_areas",
                                 "first_seen_at") and value is not None:
                    setattr(existing, field, value)

        existing.last_seen_at = now
        existing.is_new_this_run = False
        existing.content_hash = content_hash
        existing.source_run_id = source_run_id
        session.flush()
        return existing, False

    cp = CompetitorProduct(
        **{k: v for k, v in data.items()
           if k not in ("species", "support_areas")},
        source_run_id=source_run_id,
        content_hash=content_hash,
        first_seen_at=now,
        last_seen_at=now,
        is_new_this_run=True,
    )
    session.add(cp)
    session.flush()
    return cp, True


def set_competitor_species(
    session: Session, competitor_product_id: int, animal_types: list[str]
) -> None:
    session.query(CompetitorProductSpecies).filter_by(
        competitor_product_id=competitor_product_id
    ).delete()
    for at in animal_types:
        session.add(CompetitorProductSpecies(
            competitor_product_id=competitor_product_id, animal_type=at
        ))
    session.flush()


def set_competitor_support_areas(
    session: Session,
    competitor_product_id: int,
    areas: list[dict[str, Any]],
) -> None:
    session.query(CompetitorProductSupportArea).filter_by(
        competitor_product_id=competitor_product_id
    ).delete()
    for area in areas:
        session.add(CompetitorProductSupportArea(
            competitor_product_id=competitor_product_id,
            support_area=area["support_area"],
            confidence_score=area.get("confidence_score"),
            evidence_snippet=area.get("evidence_snippet"),
        ))
    session.flush()


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------
def save_gap_snapshot(
    session: Session,
    snapshot_type: str,
    dimension_key: str,
    has_coverage: bool,
    product_count: int,
    gap_priority: str | None = None,
    rationale: str | None = None,
    search_keywords: list[str] | None = None,
) -> GapAnalysisSnapshot:
    snap = GapAnalysisSnapshot(
        snapshot_type=snapshot_type,
        dimension_key=dimension_key,
        has_coverage=has_coverage,
        product_count=product_count,
        gap_priority=gap_priority,
        rationale=rationale,
        search_keywords=json.dumps(search_keywords) if search_keywords else None,
    )
    session.add(snap)
    session.flush()
    return snap
