"""Weekly recurring job: Zooplus German market competitor product discovery."""

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
from parsers.normalizer import normalize_zooplus_product
from reports.gap_analysis import run_gap_analysis
from reports.reporter import generate_competitor_report, generate_weekly_summary
from scrapers.zooplus_scraper import GERMAN_SUPPLEMENT_KEYWORDS, ZooplusScraper
from taxonomy.support_areas import SUPPORT_AREA_TAXONOMY

logger = logging.getLogger(__name__)

# German-language search term synonyms for the DE market
_GERMAN_SUPPORT_AREA_SYNONYMS: dict[str, list[str]] = {
    "joint_mobility": ["Gelenk Ergänzung", "Gelenkunterstützung", "Glucosamin Hund"],
    "skin_coat": ["Haut Fell Ergänzung", "Omega 3 Hund", "Fellpflege"],
    "digestion_gut": ["Verdauung Ergänzung", "Probiotika Hund", "Darmgesundheit"],
    "calming_stress_behavior": ["Beruhigung Hund", "Anti Stress", "Entspannung"],
    "immune_support": ["Immunsystem Ergänzung", "Abwehrkräfte", "Immunstärkung"],
    "general_wellness": ["Nahrungsergänzung", "Vitamine Hund", "Multivitamin"],
}


def _generate_german_search_terms(
    animal_types: list[str],
    support_areas: list[str] | None = None,
) -> list[dict[str, str]]:
    """Generate German-language search terms for Zooplus.

    Falls back to the standard English generator and supplements with
    German-specific terms.
    """
    terms: list[dict[str, str]] = []

    # German animal names
    animal_de = {
        "dog": "Hund",
        "cat": "Katze",
        "horse": "Pferd",
    }

    areas = support_areas or list(_GERMAN_SUPPORT_AREA_SYNONYMS.keys())

    for animal in animal_types:
        de_name = animal_de.get(animal, animal)
        for area in areas:
            synonyms = _GERMAN_SUPPORT_AREA_SYNONYMS.get(
                area, [area.replace("_", " ")]
            )
            for synonym in synonyms:
                # Replace "Hund" in templates with the actual animal
                term = synonym if de_name in synonym else f"{de_name} {synonym}"
                terms.append(
                    {
                        "search_term": term,
                        "animal_type": animal,
                        "support_area": area,
                    }
                )

        # Generic German supplement keywords
        for kw in GERMAN_SUPPLEMENT_KEYWORDS:
            terms.append(
                {
                    "search_term": f"{de_name} {kw}",
                    "animal_type": animal,
                    "support_area": "general_wellness",
                }
            )

    return terms


def run_weekly_zooplus() -> None:
    """Execute weekly Zooplus product discovery for the German market."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting weekly Zooplus discovery...")

    session = get_session()
    try:
        source_run = create_source_run(session, "zooplus", "weekly")
        session.commit()

        # Generate search terms from current portfolio gaps
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

        search_terms = _generate_german_search_terms(
            animal_types=["dog", "cat"],
            support_areas=all_areas if all_areas else None,
        )

        # Limit to reasonable number for weekly run
        search_terms = search_terms[:50]

        # Scrape Zooplus
        scraper = ZooplusScraper()
        raw_products = scraper.discover_products(
            search_terms,
            max_pages_per_search=2,
        )

        products_new = 0
        products_updated = 0

        for raw in raw_products:
            try:
                normalized = normalize_zooplus_product(raw)

                cp, is_new = upsert_competitor_product(
                    session, normalized, source_run_id=source_run.id
                )
                if is_new:
                    products_new += 1
                else:
                    products_updated += 1

                set_competitor_species(session, cp.id, normalized["_animal_types"])
                set_competitor_support_areas(
                    session, cp.id, normalized["_support_areas"]
                )

            except Exception as exc:
                logger.error(
                    "Failed to process Zooplus product '%s': %s",
                    raw.get("product_name"),
                    exc,
                )
                continue

        finish_source_run(
            session,
            source_run,
            status="completed",
            products_found=len(raw_products),
            products_new=products_new,
            products_updated=products_updated,
        )
        session.commit()

        logger.info(
            "Weekly Zooplus discovery complete: %d found, %d new, %d updated",
            len(raw_products),
            products_new,
            products_updated,
        )

        # Generate reports
        competitor_report = generate_competitor_report(session)
        reports_dir = Path(__file__).resolve().parent.parent / "reports" / "output"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "weekly_zooplus_report.txt").write_text(competitor_report)

        summary = generate_weekly_summary(session)
        (reports_dir / "weekly_zooplus_summary.txt").write_text(summary)

        logger.info("Weekly Zooplus reports saved to %s", reports_dir)
        print("\n" + competitor_report)

        # Send alerts
        try:
            from reports.alerting import send_weekly_report

            send_weekly_report(competitor_report)
        except Exception as exc:
            logger.warning("Failed to send alerts: %s", exc)

    except Exception as exc:
        logger.error("Weekly Zooplus job failed: %s", exc, exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_weekly_zooplus()
