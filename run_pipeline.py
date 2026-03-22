"""Run the full Pet Nutraceutical Intelligence pipeline.

Steps:
1. Initialize database (create tables if needed)
2. Seed data (alfavet + Chewy competitor products)
3. Run taxonomy classification (already done during seed)
4. Run gap analysis
5. Generate text reports
6. Generate HTML dashboard
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db.init_db import init_db
from db.session import get_session
from jobs.seed_data import run_seed
from reports.gap_analysis import run_gap_analysis
from reports.reporter import generate_weekly_summary
from reports.dashboard import generate_dashboard_html, save_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main() -> None:
    """Execute the full pipeline."""
    logger.info("=== Pet Nutraceutical Intelligence Pipeline ===")

    # Step 1 & 2: Seed data (also creates tables)
    logger.info("Step 1-2: Seeding database...")
    run_seed()

    # Step 3-4: Gap analysis
    logger.info("Step 3-4: Running gap analysis...")
    session = get_session()
    try:
        gap_results = run_gap_analysis(session, persist=True)
        session.commit()
        logger.info(
            "Gap analysis complete: %d products, %d gaps found",
            gap_results["total_products"],
            gap_results["gap_count"],
        )

        # Step 5: Text reports
        logger.info("Step 5: Generating text reports...")
        OUTPUT_DIR.mkdir(exist_ok=True)
        summary = generate_weekly_summary(session)
        report_path = OUTPUT_DIR / "weekly_report.txt"
        report_path.write_text(summary, encoding="utf-8")
        logger.info("Text report saved to %s", report_path)

        # Step 6: HTML dashboard
        logger.info("Step 6: Generating HTML dashboard...")
        dashboard_path = OUTPUT_DIR / "dashboard.html"
        save_dashboard(session, str(dashboard_path))
        logger.info("Dashboard saved to %s", dashboard_path)

        # Print summary to stdout
        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)
        print(f"Products seeded: {gap_results['total_products']}")
        print(f"Gaps identified: {gap_results['gap_count']}")
        print(f"Text report:     {report_path}")
        print(f"HTML dashboard:  {dashboard_path}")
        print()

        # Show top gaps
        print("Top priority gaps:")
        for gap in gap_results["prioritized_gap_list"][:5]:
            print(f"  [{gap['priority'].upper():>6}] {gap['type']}: {gap['dimension']}")
        print()

    except Exception:
        session.rollback()
        logger.exception("Pipeline failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
