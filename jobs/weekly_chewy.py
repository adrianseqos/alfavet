"""Weekly recurring job: Chewy competitor product discovery."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.search_terms import generate_search_terms
from db.crud import (
    create_source_run,
    finish_source_run,
    set_competitor_species,
    set_competitor_support_areas,
    upsert_competitor_product,
)
from db.session import get_session
from parsers.normalizer import normalize_chewy_product
from reports.gap_analysis import run_gap_analysis
from reports.reporter import generate_competitor_report, generate_weekly_summary
from scrapers.chewy_scraper import ChewyScraper
from taxonomy.support_areas import SUPPORT_AREA_TAXONOMY

logger = logging.getLogger(__name__)


def run_weekly_chewy() -> None:
    """Execute weekly Chewy product discovery."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting weekly Chewy discovery...")

    session = get_session()
    try:
        source_run = create_source_run(session, "chewy", "weekly")
        session.commit()

        # Generate search terms from current portfolio + gaps
        gap_results = run_gap_analysis(session, persist=False)

        # Build search terms from gaps
        gap_areas = [
            g["dimension"].split("__")[-1]
            for g in gap_results["prioritized_gap_list"]
            if g["type"] in ("support_area", "matrix")
            and g["dimension"] in SUPPORT_AREA_TAXONOMY
        ]
        # Also include covered areas for competitive monitoring
        covered_areas = list(gap_results["support_area_counts"].keys())
        all_areas = list(set(gap_areas + covered_areas))

        search_terms = generate_search_terms(
            animal_types=["dog", "cat"],
            support_areas=all_areas if all_areas else None,
        )

        # Limit to reasonable number for weekly run
        search_terms = search_terms[:50]

        # Scrape Chewy
        scraper = ChewyScraper()
        raw_products = scraper.discover_products(
            search_terms,
            max_pages_per_search=2,
            fetch_details=False,
        )

        products_new = 0
        products_updated = 0

        for raw in raw_products:
            try:
                normalized = normalize_chewy_product(raw)

                cp, is_new = upsert_competitor_product(
                    session, normalized, source_run_id=source_run.id
                )
                if is_new:
                    products_new += 1
                else:
                    products_updated += 1

                set_competitor_species(session, cp.id, normalized["_animal_types"])
                set_competitor_support_areas(session, cp.id, normalized["_support_areas"])

            except Exception as exc:
                logger.error(
                    "Failed to process Chewy product '%s': %s",
                    raw.get("product_name"), exc,
                )
                continue

        finish_source_run(
            session, source_run,
            status="completed",
            products_found=len(raw_products),
            products_new=products_new,
            products_updated=products_updated,
        )
        session.commit()

        logger.info(
            "Weekly Chewy discovery complete: %d found, %d new, %d updated",
            len(raw_products), products_new, products_updated,
        )

        # Generate reports
        competitor_report = generate_competitor_report(session)
        reports_dir = Path(__file__).resolve().parent.parent / "reports" / "output"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "weekly_competitor_report.txt").write_text(competitor_report)

        summary = generate_weekly_summary(session)
        (reports_dir / "weekly_summary.txt").write_text(summary)

        logger.info("Weekly reports saved to %s", reports_dir)
        print("\n" + competitor_report)

        # Send alerts
        try:
            from reports.alerting import send_weekly_report
            send_weekly_report(competitor_report)
        except Exception as exc:
            logger.warning("Failed to send alerts: %s", exc)

    except Exception as exc:
        logger.error("Weekly Chewy job failed: %s", exc, exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_weekly_chewy()
