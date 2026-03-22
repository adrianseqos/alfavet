"""One-time bootstrap job: scrape and ingest alfavet portfolio."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.crud import (
    create_source_run,
    finish_source_run,
    set_product_ingredients,
    set_product_species,
    set_product_support_areas,
    upsert_product,
)
from db.session import get_session
from parsers.normalizer import normalize_alfavet_product
from reports.gap_analysis import run_gap_analysis
from reports.reporter import generate_gap_report, generate_portfolio_report
from scrapers.alfavet_scraper import AlfavetScraper

logger = logging.getLogger(__name__)


def run_bootstrap() -> None:
    """Execute the one-time alfavet portfolio scrape and analysis."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting alfavet bootstrap scrape...")

    session = get_session()
    try:
        # Create source run
        source_run = create_source_run(session, "alfavet", "bootstrap")
        session.commit()

        # Scrape
        scraper = AlfavetScraper()
        raw_products = scraper.scrape_all()

        products_new = 0
        products_updated = 0

        for raw in raw_products:
            try:
                normalized = normalize_alfavet_product(raw)

                # Upsert product
                product, is_new = upsert_product(session, normalized)
                if is_new:
                    products_new += 1
                else:
                    products_updated += 1

                # Set relational data
                set_product_species(session, product.id, normalized["_animal_types"])
                set_product_support_areas(
                    session, product.id,
                    normalized["_support_areas"],
                    raw_condition=normalized.get("_condition_raw"),
                )
                set_product_ingredients(session, product.id, normalized["_ingredients_parsed"])

            except Exception as exc:
                logger.error("Failed to process product '%s': %s", raw.get("product_name"), exc)
                continue

        # Finalize source run
        finish_source_run(
            session, source_run,
            status="completed",
            products_found=len(raw_products),
            products_new=products_new,
            products_updated=products_updated,
        )
        session.commit()

        logger.info(
            "Bootstrap complete: %d found, %d new, %d updated",
            len(raw_products), products_new, products_updated,
        )

        # Run gap analysis
        logger.info("Running gap analysis...")
        gap_results = run_gap_analysis(session, persist=True)
        session.commit()

        # Generate reports
        portfolio_report = generate_portfolio_report(session)
        gap_report = generate_gap_report(session)

        # Save reports to files
        reports_dir = Path(__file__).resolve().parent.parent / "reports" / "output"
        reports_dir.mkdir(parents=True, exist_ok=True)

        (reports_dir / "portfolio_report.txt").write_text(portfolio_report)
        (reports_dir / "gap_report.txt").write_text(gap_report)

        logger.info("Reports saved to %s", reports_dir)
        print("\n" + portfolio_report)
        print("\n" + gap_report)

    except Exception as exc:
        logger.error("Bootstrap failed: %s", exc, exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_bootstrap()
