"""APScheduler-based weekly job scheduler."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import (
    SOURCE_CHEWY_ENABLED,
    WEEKLY_SCHEDULE_DAY,
    WEEKLY_SCHEDULE_HOUR,
    WEEKLY_SCHEDULE_MINUTE,
)

logger = logging.getLogger(__name__)


def _run_chewy_job() -> None:
    """Wrapper for weekly Chewy job."""
    from jobs.weekly_chewy import run_weekly_chewy

    try:
        run_weekly_chewy()
    except Exception as exc:
        logger.error("Chewy weekly job failed: %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Start the weekly job scheduler."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scheduler = BlockingScheduler()

    if SOURCE_CHEWY_ENABLED:
        scheduler.add_job(
            _run_chewy_job,
            trigger=CronTrigger(
                day_of_week=WEEKLY_SCHEDULE_DAY,
                hour=WEEKLY_SCHEDULE_HOUR,
                minute=WEEKLY_SCHEDULE_MINUTE,
            ),
            id="chewy_weekly",
            name="Weekly Chewy Discovery",
            replace_existing=True,
        )
        logger.info(
            "Scheduled Chewy weekly discovery: %s at %02d:%02d",
            WEEKLY_SCHEDULE_DAY, WEEKLY_SCHEDULE_HOUR, WEEKLY_SCHEDULE_MINUTE,
        )
    else:
        logger.info("Chewy source is disabled; no job scheduled.")

    logger.info("Scheduler started. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    start_scheduler()
