"""Reporting module: generates portfolio, gap, and competitor reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    ChangeLog,
    CompetitorProduct,
    CompetitorProductSpecies,
    CompetitorProductSupportArea,
    Product,
    ProductSpecies,
    ProductSupportArea,
    SourceRun,
)
from reports.gap_analysis import run_gap_analysis
from taxonomy.support_areas import ANIMAL_TYPES, SUPPORT_AREA_TAXONOMY

logger = logging.getLogger(__name__)


def _format_matrix(matrix: dict[str, dict[str, int]], row_labels: list[str], col_labels: list[str]) -> str:
    """Format a coverage matrix as a text table."""
    out = StringIO()
    # Header
    col_width = 12
    out.write(f"{'':>18}")
    for col in col_labels:
        short = col[:col_width]
        out.write(f"{short:>{col_width}}")
    out.write("\n")
    out.write("-" * (18 + col_width * len(col_labels)) + "\n")

    for row in row_labels:
        out.write(f"{row:>18}")
        for col in col_labels:
            val = matrix.get(row, {}).get(col, 0)
            marker = str(val) if val > 0 else "  -"
            out.write(f"{marker:>{col_width}}")
        out.write("\n")

    return out.getvalue()


def generate_portfolio_report(session: Session) -> str:
    """Generate current alfavet portfolio coverage report."""
    out = StringIO()
    out.write("=" * 70 + "\n")
    out.write("ALFAVET PORTFOLIO COVERAGE REPORT\n")
    out.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    out.write("=" * 70 + "\n\n")

    # Product count
    total = session.execute(select(func.count(Product.id))).scalar() or 0
    out.write(f"Total products: {total}\n\n")

    # By animal type
    out.write("--- Products by Animal Type ---\n")
    animal_counts = session.execute(
        select(ProductSpecies.animal_type, func.count(ProductSpecies.product_id))
        .group_by(ProductSpecies.animal_type)
        .order_by(func.count(ProductSpecies.product_id).desc())
    ).all()
    for animal, count in animal_counts:
        out.write(f"  {animal:>20}: {count}\n")
    out.write("\n")

    # By support area
    out.write("--- Products by Support Area ---\n")
    area_counts = session.execute(
        select(ProductSupportArea.support_area, func.count(ProductSupportArea.product_id))
        .group_by(ProductSupportArea.support_area)
        .order_by(func.count(ProductSupportArea.product_id).desc())
    ).all()
    for area, count in area_counts:
        label = SUPPORT_AREA_TAXONOMY.get(area, {}).get("label", area)
        out.write(f"  {label:>35}: {count}\n")
    out.write("\n")

    # By form factor
    out.write("--- Products by Form Factor ---\n")
    form_counts = session.execute(
        select(Product.form_factor, func.count(Product.id))
        .where(Product.form_factor.isnot(None))
        .group_by(Product.form_factor)
        .order_by(func.count(Product.id).desc())
    ).all()
    for form, count in form_counts:
        out.write(f"  {form:>20}: {count}\n")
    out.write("\n")

    # Product list
    out.write("--- Product List ---\n")
    products = session.execute(
        select(Product).order_by(Product.product_name)
    ).scalars().all()
    for p in products:
        species = [s.animal_type for s in p.species]
        areas = [a.support_area for a in p.support_areas]
        out.write(f"\n  {p.product_name}\n")
        out.write(f"    Brand: {p.brand or 'N/A'}\n")
        out.write(f"    URL: {p.product_url}\n")
        out.write(f"    Species: {', '.join(species)}\n")
        out.write(f"    Support areas: {', '.join(areas)}\n")
        out.write(f"    Form: {p.form_factor or 'N/A'} | Pack: {p.pack_size or 'N/A'}\n")
        if p.price:
            out.write(f"    Price: {p.price} {p.currency}\n")

    return out.getvalue()


def generate_gap_report(session: Session) -> str:
    """Generate gap analysis report."""
    analysis = run_gap_analysis(session, persist=False)
    out = StringIO()

    out.write("=" * 70 + "\n")
    out.write("PORTFOLIO GAP ANALYSIS REPORT\n")
    out.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    out.write("=" * 70 + "\n\n")

    out.write(f"Total alfavet products: {analysis['total_products']}\n")
    out.write(f"Gaps identified: {analysis['gap_count']}\n\n")

    # Coverage matrix
    out.write("--- Animal Type × Support Area Matrix ---\n")
    animals_to_show = [a for a in ANIMAL_TYPES if a not in ("unknown", "multi-species")]
    areas_to_show = [a for a in SUPPORT_AREA_TAXONOMY if a not in ("other", "unknown")]
    out.write(_format_matrix(analysis["coverage_matrix"], animals_to_show, areas_to_show))
    out.write("\n")

    # Prioritized gaps
    out.write("--- Prioritized Gap List ---\n\n")
    for i, gap in enumerate(analysis["prioritized_gap_list"], 1):
        out.write(f"  {i}. [{gap['priority'].upper()}] {gap['type']}: {gap['dimension']}\n")
        out.write(f"     Rationale: {gap['rationale']}\n")
        out.write(f"     Search keywords: {', '.join(gap['search_keywords'][:3])}\n\n")

    # Ingredient summary
    out.write("--- Top Ingredient Families ---\n")
    for ing, count in list(analysis["ingredient_families"].items())[:15]:
        out.write(f"  {ing:>30}: {count}\n")

    return out.getvalue()


def generate_competitor_report(session: Session, days: int = 7) -> str:
    """Generate competitor discovery report for the last N days."""
    out = StringIO()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    out.write("=" * 70 + "\n")
    out.write(f"COMPETITOR DISCOVERY REPORT (last {days} days)\n")
    out.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    out.write("=" * 70 + "\n\n")

    # New products
    new_products = session.execute(
        select(CompetitorProduct)
        .where(CompetitorProduct.first_seen_at >= cutoff)
        .order_by(CompetitorProduct.first_seen_at.desc())
    ).scalars().all()

    out.write(f"New products discovered: {len(new_products)}\n\n")

    if new_products:
        out.write("--- Newly Discovered Products ---\n")
        for p in new_products:
            species = [s.animal_type for s in p.species]
            areas = [a.support_area for a in p.support_areas]
            out.write(f"\n  {p.product_name}\n")
            out.write(f"    Source: {p.source} | Brand: {p.brand or 'N/A'}\n")
            out.write(f"    URL: {p.product_url}\n")
            out.write(f"    Species: {', '.join(species)}\n")
            out.write(f"    Support areas: {', '.join(areas)}\n")
            out.write(f"    Price: {p.price} {p.currency or ''}\n")
            if p.rating:
                out.write(f"    Rating: {p.rating} ({p.review_count or 0} reviews)\n")
            out.write(f"    Search term: {p.search_term}\n")
        out.write("\n")

    # Changes
    changes = session.execute(
        select(ChangeLog)
        .where(ChangeLog.changed_at >= cutoff)
        .order_by(ChangeLog.changed_at.desc())
    ).scalars().all()

    if changes:
        out.write(f"--- Price/Availability Changes ({len(changes)}) ---\n")
        for c in changes[:20]:
            out.write(
                f"  [{c.entity_type} #{c.entity_id}] {c.field_name}: "
                f"'{c.old_value}' -> '{c.new_value}'\n"
            )

    # Source run summary
    runs = session.execute(
        select(SourceRun)
        .where(SourceRun.started_at >= cutoff)
        .order_by(SourceRun.started_at.desc())
    ).scalars().all()
    if runs:
        out.write(f"\n--- Source Runs ---\n")
        for r in runs:
            out.write(
                f"  {r.source} ({r.run_type}): {r.status} | "
                f"found={r.products_found}, new={r.products_new}, "
                f"updated={r.products_updated}\n"
            )

    return out.getvalue()


def generate_weekly_summary(session: Session) -> str:
    """Generate combined weekly summary report."""
    parts = [
        generate_portfolio_report(session),
        "\n\n",
        generate_gap_report(session),
        "\n\n",
        generate_competitor_report(session),
    ]
    return "".join(parts)
