"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/pet_nutra_intel"
)
DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"

# Scraping
SCRAPE_RATE_LIMIT: float = float(os.getenv("SCRAPE_RATE_LIMIT_SECONDS", "2.0"))
SCRAPE_MAX_RETRIES: int = int(os.getenv("SCRAPE_MAX_RETRIES", "3"))
SCRAPE_TIMEOUT: int = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "30"))
SCRAPE_USER_AGENT: str = os.getenv(
    "SCRAPE_USER_AGENT",
    "PetNutraIntel/1.0 (market-research; contact@alfavet.de)",
)
SCRAPE_POLITE_CONCURRENCY: int = int(os.getenv("SCRAPE_POLITE_CONCURRENCY", "2"))

# Sources
ALFAVET_BASE_URL: str = os.getenv("ALFAVET_BASE_URL", "https://alfavet.de/")
CHEWY_BASE_URL: str = os.getenv("CHEWY_BASE_URL", "https://www.chewy.com/")

# Scheduler
WEEKLY_SCHEDULE_DAY: str = os.getenv("WEEKLY_SCHEDULE_DAY", "monday")
WEEKLY_SCHEDULE_HOUR: int = int(os.getenv("WEEKLY_SCHEDULE_HOUR", "6"))
WEEKLY_SCHEDULE_MINUTE: int = int(os.getenv("WEEKLY_SCHEDULE_MINUTE", "0"))

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "pet_nutra_intel.log"))

# Feature flags
SOURCE_ALFAVET_ENABLED: bool = os.getenv("SOURCE_ALFAVET_ENABLED", "true").lower() == "true"
SOURCE_CHEWY_ENABLED: bool = os.getenv("SOURCE_CHEWY_ENABLED", "true").lower() == "true"
