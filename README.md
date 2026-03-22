# Pet Nutraceutical Portfolio Intelligence System

Market intelligence system for analyzing the alfavet.de pet nutraceutical portfolio, identifying coverage gaps, and discovering competitor products on Chewy.com.

## Architecture

```
├── scrapers/          # Web scraping modules (alfavet, Chewy)
│   ├── base.py        # Base scraper with rate limiting, robots.txt, retry
│   ├── alfavet_scraper.py  # alfavet.de portfolio scraper
│   └── chewy_scraper.py    # Chewy.com competitor discovery
├── parsers/           # Data normalization
│   └── normalizer.py  # Cleans and standardizes scraped data
├── taxonomy/          # Classification system
│   ├── support_areas.py    # Standardized taxonomy definitions
│   └── classifier.py       # Multi-label classifier for support areas, species, etc.
├── db/                # Database layer
│   ├── models.py      # SQLAlchemy ORM models (10 tables)
│   ├── crud.py        # CRUD operations with change tracking
│   ├── session.py     # DB session management
│   ├── init_db.py     # Schema initialization script
│   └── migrations/    # Alembic migrations
├── jobs/              # Scheduled and one-time jobs
│   ├── bootstrap_alfavet.py  # One-time portfolio scrape
│   ├── weekly_chewy.py       # Recurring weekly competitor discovery
│   └── scheduler.py          # APScheduler weekly job runner
├── reports/           # Analysis and reporting
│   ├── gap_analysis.py    # Portfolio gap identification engine
│   └── reporter.py        # Report generators (portfolio, gap, competitor, weekly)
├── tests/             # Test suite
├── config/            # Configuration
│   ├── settings.py    # Environment-based settings
│   └── search_terms.py    # Search term generation for competitor discovery
└── .env.example       # Configuration template
```

## Database Schema

10 tables supporting the full workflow:

| Table | Purpose |
|-------|---------|
| `products` | alfavet portfolio products |
| `product_species` | Animal type mappings (multi-label) |
| `product_support_areas` | Support area classifications with confidence scores |
| `product_ingredients` | Parsed ingredients |
| `competitor_products` | Chewy discovered products |
| `competitor_product_species` | Competitor animal type mappings |
| `competitor_product_support_areas` | Competitor support area mappings |
| `source_runs` | Scrape execution audit trail |
| `gap_analysis_snapshots` | Point-in-time gap analysis results |
| `change_log` | Field-level change history |

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+

### Installation

```bash
# Clone and install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# Initialize database
python db/init_db.py
# Or use Alembic: alembic upgrade head
```

## Running

### One-Time Bootstrap (alfavet portfolio)

```bash
python jobs/bootstrap_alfavet.py
```

This will:
1. Scrape all products from alfavet.de
2. Classify each product (species, support areas, form factor, life stage)
3. Store normalized data in PostgreSQL
4. Run gap analysis
5. Generate portfolio and gap reports in `reports/output/`

### Weekly Competitor Discovery (Chewy)

```bash
# Run once manually
python jobs/weekly_chewy.py

# Start recurring scheduler (runs every Monday at 06:00)
python jobs/scheduler.py
```

The weekly job will:
1. Generate search terms from portfolio coverage + gaps
2. Search Chewy for matching nutraceutical products
3. Detect new vs. existing products
4. Track price, rating, and availability changes
5. Generate weekly summary report

### Generate Reports

Reports are automatically generated during bootstrap and weekly runs. Output is saved to `reports/output/`.

### Run Tests

```bash
pytest tests/ -v
```

## Configuration

All settings are in `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql://... | PostgreSQL connection string |
| `SCRAPE_RATE_LIMIT_SECONDS` | 2.0 | Minimum seconds between requests |
| `SCRAPE_MAX_RETRIES` | 3 | Retry count per URL |
| `WEEKLY_SCHEDULE_DAY` | monday | Day of week for recurring jobs |
| `SOURCE_CHEWY_ENABLED` | true | Enable/disable Chewy scraping |

## Taxonomy

Products are classified using a standardized taxonomy of 22 support areas:

`joint_mobility`, `skin_coat`, `digestion_gut`, `calming_stress_behavior`, `immune_support`, `urinary_renal`, `dental_oral`, `weight_management`, `allergy_sensitivity`, `senior_support`, `puppy_kitten_growth`, `cardiovascular`, `liver_support`, `cognitive_brain`, `eye_vision`, `bone_mineral`, `recovery_convalescence`, `muscle_performance`, `parasite_repellent_non_drug`, `general_wellness`, `other`, `unknown`

Classification uses keyword matching on product names, descriptions, and ingredients with confidence scoring. Both German and English keywords are supported.

## Legal/Technical Constraints

- Respects `robots.txt` for all sources
- Configurable rate limiting (default 2s between requests)
- Retry with exponential backoff on failures
- Sources can be individually disabled via feature flags
- No login-only areas or anti-bot circumvention
- No CAPTCHA solving

## Known Limitations

- Classification accuracy depends on product page content quality
- Some alfavet.de pages may use JavaScript-heavy rendering (consider Playwright for improved coverage)
- Chewy search results may vary; structured data extraction depends on page structure
- Price tracking requires consistent page structure across runs
- Gap analysis uses predefined "common" categories; market-specific weightings may need tuning
