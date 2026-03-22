"""Web dashboard and standalone HTML report generator for the pet
nutraceutical intelligence system.

Generates a self-contained HTML file with:
- Portfolio coverage matrix (animal type x support area) as a heatmap table
- Gap list with priority colours
- Competitor product comparison table
- Ingredient trend chart (inline CSS bar chart, no JS dependencies)
- Weekly change summary

When Flask is available the module also exposes a minimal web app; otherwise
only the static HTML generation functions are provided.
"""

from __future__ import annotations

import html as html_mod
import logging
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    ChangeLog,
    CompetitorProduct,
    CompetitorProductSpecies,
    CompetitorProductSupportArea,
    Product,
    ProductIngredient,
    ProductSpecies,
    ProductSupportArea,
)
from reports.gap_analysis import run_gap_analysis
from taxonomy.support_areas import ANIMAL_TYPES, SUPPORT_AREA_TAXONOMY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_PRIORITY_COLOURS: dict[str, str] = {
    "high": "#e74c3c",
    "medium": "#f39c12",
    "low": "#2ecc71",
}


def _heatmap_colour(value: int, max_value: int) -> str:
    """Return a CSS background colour for a heatmap cell."""
    if value == 0:
        return "#f8f9fa"
    if max_value == 0:
        max_value = 1
    ratio = min(value / max_value, 1.0)
    # Gradient from light green to dark green
    r = int(232 - ratio * 140)
    g = int(245 - ratio * 60)
    b = int(233 - ratio * 140)
    return f"rgb({r},{g},{b})"


# ---------------------------------------------------------------------------
# HTML template parts
# ---------------------------------------------------------------------------

_CSS = """\
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       margin: 0; padding: 20px 40px; background: #f4f6f9; color: #2c3e50; }
h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
h2 { color: #34495e; margin-top: 35px; }
table { border-collapse: collapse; width: 100%; margin: 15px 0; }
th, td { border: 1px solid #dee2e6; padding: 8px 12px; text-align: left; font-size: 14px; }
th { background: #3498db; color: #fff; font-weight: 600; }
tr:nth-child(even) { background: #f8f9fa; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
         color: #fff; font-size: 12px; font-weight: 600; }
.badge-high { background: #e74c3c; }
.badge-medium { background: #f39c12; }
.badge-low { background: #2ecc71; }
.bar-chart { margin: 15px 0; }
.bar-row { display: flex; align-items: center; margin: 4px 0; }
.bar-label { width: 200px; text-align: right; padding-right: 10px; font-size: 13px;
             overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-fill { height: 22px; background: #3498db; border-radius: 3px;
            min-width: 2px; transition: width 0.3s; }
.bar-value { padding-left: 8px; font-size: 12px; color: #7f8c8d; }
.summary-box { background: #fff; border-radius: 8px; padding: 20px;
               margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.stat { display: inline-block; text-align: center; margin: 0 25px; }
.stat-number { font-size: 36px; font-weight: 700; color: #3498db; }
.stat-label { font-size: 13px; color: #7f8c8d; }
.footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #dee2e6;
          font-size: 12px; color: #95a5a6; }
"""


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html_mod.escape(str(text))


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_header(timestamp: str) -> str:
    return (
        f"<h1>Pet Nutraceutical Intelligence Dashboard</h1>\n"
        f"<p>Generated: {_esc(timestamp)}</p>\n"
    )


def _build_summary_stats(analysis: dict[str, Any]) -> str:
    total = analysis.get("total_products", 0)
    gaps = analysis.get("gap_count", 0)
    areas_covered = len(analysis.get("support_area_counts", {}))
    animals_covered = len(analysis.get("animal_type_counts", {}))

    return (
        '<div class="summary-box">\n'
        f'  <div class="stat"><div class="stat-number">{total}</div>'
        f'<div class="stat-label">Portfolio Products</div></div>\n'
        f'  <div class="stat"><div class="stat-number">{gaps}</div>'
        f'<div class="stat-label">Gaps Identified</div></div>\n'
        f'  <div class="stat"><div class="stat-number">{areas_covered}</div>'
        f'<div class="stat-label">Support Areas Covered</div></div>\n'
        f'  <div class="stat"><div class="stat-number">{animals_covered}</div>'
        f'<div class="stat-label">Animal Types Covered</div></div>\n'
        "</div>\n"
    )


def _build_coverage_matrix(analysis: dict[str, Any]) -> str:
    """Build an HTML heatmap table for the coverage matrix."""
    matrix = analysis.get("coverage_matrix", {})
    animals = [a for a in ANIMAL_TYPES if a not in ("unknown", "multi-species")]
    areas = [a for a in SUPPORT_AREA_TAXONOMY if a not in ("other", "unknown")]

    # Find max value for colour scaling
    max_val = 1
    for animal in animals:
        for area in areas:
            val = matrix.get(animal, {}).get(area, 0)
            if val > max_val:
                max_val = val

    out = StringIO()
    out.write("<h2>Portfolio Coverage Matrix</h2>\n")
    out.write('<div style="overflow-x: auto;">\n<table>\n<tr><th></th>\n')
    for area in areas:
        label = SUPPORT_AREA_TAXONOMY[area].get("label", area)
        short = label[:18]
        out.write(
            f'<th style="font-size:11px; writing-mode:vertical-rl; '
            f'text-orientation:mixed; height:120px;">{_esc(short)}</th>\n'
        )
    out.write("</tr>\n")

    for animal in animals:
        out.write(f"<tr><td><strong>{_esc(animal)}</strong></td>\n")
        for area in areas:
            val = matrix.get(animal, {}).get(area, 0)
            bg = _heatmap_colour(val, max_val)
            text_colour = "#fff" if val > max_val * 0.5 else "#2c3e50"
            display = str(val) if val > 0 else "-"
            out.write(
                f'<td style="background:{bg}; color:{text_colour}; '
                f'text-align:center; font-weight:600;">{display}</td>\n'
            )
        out.write("</tr>\n")
    out.write("</table>\n</div>\n")
    return out.getvalue()


def _build_gap_list(analysis: dict[str, Any]) -> str:
    """Build the prioritized gap list as an HTML table."""
    gaps = analysis.get("prioritized_gap_list", [])
    if not gaps:
        return "<h2>Gap List</h2>\n<p>No gaps identified.</p>\n"

    out = StringIO()
    out.write("<h2>Gap List</h2>\n<table>\n")
    out.write("<tr><th>#</th><th>Priority</th><th>Type</th>"
              "<th>Dimension</th><th>Rationale</th></tr>\n")

    for i, gap in enumerate(gaps, 1):
        priority = gap.get("priority", "low")
        badge_cls = f"badge-{priority}"
        out.write(
            f"<tr><td>{i}</td>"
            f'<td><span class="badge {badge_cls}">{_esc(priority.upper())}</span></td>'
            f"<td>{_esc(gap.get('type', ''))}</td>"
            f"<td>{_esc(gap.get('dimension', ''))}</td>"
            f"<td>{_esc(gap.get('rationale', ''))}</td></tr>\n"
        )
    out.write("</table>\n")
    return out.getvalue()


def _build_competitor_table(session: Session, days: int = 7) -> str:
    """Build an HTML table of recently discovered competitor products."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    products = session.execute(
        select(CompetitorProduct)
        .where(CompetitorProduct.first_seen_at >= cutoff)
        .order_by(CompetitorProduct.first_seen_at.desc())
    ).scalars().all()

    out = StringIO()
    out.write(f"<h2>Competitor Products (last {days} days)</h2>\n")
    if not products:
        out.write("<p>No new competitor products discovered.</p>\n")
        return out.getvalue()

    out.write("<table>\n<tr><th>Product</th><th>Brand</th><th>Source</th>"
              "<th>Price</th><th>Rating</th><th>Reviews</th></tr>\n")

    for p in products[:50]:  # Limit display
        price_str = f"{p.price:.2f} {p.currency or ''}" if p.price else "-"
        rating_str = f"{p.rating:.1f}" if p.rating else "-"
        review_str = str(p.review_count) if p.review_count else "-"
        name_html = (
            f'<a href="{_esc(p.product_url)}" target="_blank">'
            f"{_esc(p.product_name[:60])}</a>"
            if p.product_url
            else _esc(p.product_name[:60])
        )
        out.write(
            f"<tr><td>{name_html}</td><td>{_esc(p.brand or '-')}</td>"
            f"<td>{_esc(p.source)}</td><td>{price_str}</td>"
            f"<td>{rating_str}</td><td>{review_str}</td></tr>\n"
        )
    out.write("</table>\n")
    return out.getvalue()


def _build_ingredient_chart(analysis: dict[str, Any]) -> str:
    """Build a simple CSS-only bar chart of top ingredients."""
    ingredients = analysis.get("ingredient_families", {})
    if not ingredients:
        return "<h2>Ingredient Trends</h2>\n<p>No ingredient data available.</p>\n"

    top_items = list(ingredients.items())[:15]
    max_count = max(count for _, count in top_items) if top_items else 1

    out = StringIO()
    out.write("<h2>Ingredient Trends</h2>\n")
    out.write('<div class="bar-chart">\n')
    for name, count in top_items:
        width_pct = (count / max_count) * 100
        out.write(
            f'<div class="bar-row">'
            f'<div class="bar-label">{_esc(name)}</div>'
            f'<div class="bar-fill" style="width:{width_pct:.0f}%;"></div>'
            f'<div class="bar-value">{count}</div>'
            f"</div>\n"
        )
    out.write("</div>\n")
    return out.getvalue()


def _build_change_summary(session: Session, days: int = 7) -> str:
    """Build the weekly change summary section."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    changes = session.execute(
        select(ChangeLog)
        .where(ChangeLog.changed_at >= cutoff)
        .order_by(ChangeLog.changed_at.desc())
    ).scalars().all()

    out = StringIO()
    out.write("<h2>Weekly Change Summary</h2>\n")
    if not changes:
        out.write("<p>No changes detected in the last week.</p>\n")
        return out.getvalue()

    out.write(f"<p>{len(changes)} change(s) detected.</p>\n")
    out.write("<table>\n<tr><th>Entity</th><th>Field</th>"
              "<th>Old Value</th><th>New Value</th><th>When</th></tr>\n")

    for c in changes[:30]:
        when = c.changed_at.strftime("%Y-%m-%d %H:%M") if c.changed_at else "-"
        out.write(
            f"<tr><td>{_esc(c.entity_type)} #{c.entity_id}</td>"
            f"<td>{_esc(c.field_name)}</td>"
            f"<td>{_esc(str(c.old_value or '-')[:60])}</td>"
            f"<td>{_esc(str(c.new_value or '-')[:60])}</td>"
            f"<td>{when}</td></tr>\n"
        )
    out.write("</table>\n")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_dashboard_html(session: Session) -> str:
    """Generate a self-contained HTML dashboard from the current database state.

    Parameters
    ----------
    session:
        An active SQLAlchemy session.

    Returns
    -------
    str
        A complete HTML document string.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    analysis = run_gap_analysis(session, persist=False)

    parts = [
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n",
        "<meta charset=\"UTF-8\">\n",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n",
        "<title>Pet Nutraceutical Intelligence Dashboard</title>\n",
        f"<style>\n{_CSS}</style>\n",
        "</head>\n<body>\n",
        _build_header(timestamp),
        _build_summary_stats(analysis),
        _build_coverage_matrix(analysis),
        _build_gap_list(analysis),
        _build_competitor_table(session),
        _build_ingredient_chart(analysis),
        _build_change_summary(session),
        f'<div class="footer">Pet Nutraceutical Intelligence System &mdash; '
        f"Generated {_esc(timestamp)}</div>\n",
        "</body>\n</html>",
    ]
    return "".join(parts)


def save_dashboard(session: Session, output_path: str | Path) -> Path:
    """Generate the dashboard HTML and write it to *output_path*.

    Parameters
    ----------
    session:
        An active SQLAlchemy session.
    output_path:
        File path for the output HTML.

    Returns
    -------
    Path
        The resolved output path.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    html_content = generate_dashboard_html(session)
    output.write_text(html_content, encoding="utf-8")
    logger.info("Dashboard saved to %s (%d bytes)", output, len(html_content))
    return output.resolve()


# ---------------------------------------------------------------------------
# Optional Flask app
# ---------------------------------------------------------------------------

def create_flask_app() -> Any:
    """Create a minimal Flask app that serves the dashboard.

    Returns ``None`` if Flask is not installed.
    """
    try:
        from flask import Flask, Response
    except ImportError:
        logger.info("Flask is not installed — web dashboard not available.")
        return None

    from db.session import get_session

    app = Flask(__name__)

    @app.route("/")
    def index() -> Response:
        session = get_session()
        try:
            html_content = generate_dashboard_html(session)
            return Response(html_content, mimetype="text/html")
        finally:
            session.close()

    @app.route("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


# Allow running directly: python -m reports.dashboard
if __name__ == "__main__":
    app = create_flask_app()
    if app is not None:
        app.run(host="0.0.0.0", port=5050, debug=True)
    else:
        print("Flask not available. Use save_dashboard() for static HTML generation.")
