"""Seed the database with representative alfavet products and competitor data.

Uses realistic product data based on alfavet.de portfolio and competitor
market data. This allows the full pipeline (classification, gap analysis,
reporting, dashboard) to run end-to-end without live scraping.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.crud import (
    create_source_run,
    finish_source_run,
    set_competitor_species,
    set_competitor_support_areas,
    set_product_ingredients,
    set_product_species,
    set_product_support_areas,
    upsert_competitor_product,
    upsert_product,
)
from db.init_db import init_db
from db.session import get_session
from parsers.normalizer import (
    normalize_alfavet_product,
    normalize_chewy_product,
    parse_ingredients,
)
from taxonomy.classifier import classify_product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alfavet product catalogue (representative subset)
# ---------------------------------------------------------------------------
ALFAVET_PRODUCTS = [
    {
        "product_name": "alfavet ReConvales Tonicum Katze",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/reconvales-tonicum-katze",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Diät-Ergänzungsfuttermittel",
        "active_ingredients_raw": "Taurin, L-Arginin, Omega-3-Fettsäuren, Vitamin B-Komplex, Zink",
        "claimed_benefits_raw": "Rekonvaleszenz, Appetitanregung, Immunstärkung, Aufbaukur nach Krankheit",
        "pack_size": "6 x 90 ml",
        "price": 29.90,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Flüssiges Diät-Ergänzungsfuttermittel für Katzen zur Rekonvaleszenz und Appetitanregung",
        "_body_text": "Reconvales Tonicum Katze unterstützt die Genesung nach Krankheit und Operation",
        "_ingredients_text": "Taurin, L-Arginin, Omega-3-Fettsäuren, Vitamin B-Komplex, Zink, Eisen",
    },
    {
        "product_name": "alfavet ReConvales Tonicum Hund",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/reconvales-tonicum-hund",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Diät-Ergänzungsfuttermittel",
        "active_ingredients_raw": "L-Carnitin, Omega-3-Fettsäuren, Vitamin B-Komplex, Zink, Eisen",
        "claimed_benefits_raw": "Rekonvaleszenz, Appetitanregung, Aufbaukur, Stärkung nach Krankheit",
        "pack_size": "6 x 90 ml",
        "price": 29.90,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Flüssiges Diät-Ergänzungsfuttermittel für Hunde zur Rekonvaleszenz",
        "_body_text": "Reconvales Tonicum Hund unterstützt die Genesung und regt den Appetit an",
        "_ingredients_text": "L-Carnitin, Omega-3-Fettsäuren, Vitamin B-Komplex, Zink, Eisen",
    },
    {
        "product_name": "alfavet ReConvales Power Katze",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/reconvales-power-katze",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Diät-Ergänzungsfuttermittel",
        "active_ingredients_raw": "Hochverdauliches Protein, MCT-Öl, Taurin, L-Arginin, Vitamine A D E",
        "claimed_benefits_raw": "Intensive Ernährung, Rekonvaleszenz, Energieversorgung bei Anorexie",
        "pack_size": "6 x 90 g",
        "price": 32.50,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Hochkalorisches Ergänzungsfuttermittel Paste für Katzen",
        "_body_text": "Reconvales Power ist eine hochkalorische Paste für Katzen in Rekonvaleszenz",
        "_ingredients_text": "Hochverdauliches Protein, MCT-Öl, Taurin, L-Arginin, Vitamine",
    },
    {
        "product_name": "alfavet ReConvales Power Hund",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/reconvales-power-hund",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Diät-Ergänzungsfuttermittel",
        "active_ingredients_raw": "Hochverdauliches Protein, MCT-Öl, L-Carnitin, Vitamine A D E",
        "claimed_benefits_raw": "Intensive Ernährung, Rekonvaleszenz, Energieversorgung",
        "pack_size": "6 x 90 g",
        "price": 32.50,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Hochkalorisches Ergänzungsfuttermittel Paste für Hunde",
        "_body_text": "Reconvales Power unterstützt Hunde mit erhöhtem Energiebedarf",
        "_ingredients_text": "Hochverdauliches Protein, MCT-Öl, L-Carnitin, Vitamine",
    },
    {
        "product_name": "alfavet DiarDoc Pro Paste",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/diardoc-pro-paste",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Diät-Ergänzungsfuttermittel",
        "active_ingredients_raw": "Probiotika (Enterococcus faecium), Pektine, Bentonit, Elektrolyte",
        "claimed_benefits_raw": "Durchfallbehandlung, Darmflora-Stabilisierung, Verdauungsunterstützung",
        "pack_size": "24 ml Dosierspritze",
        "price": 12.50,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Diätetisches Ergänzungsfuttermittel zur Stabilisierung der Darmflora bei Hund und Katze",
        "_body_text": "DiarDoc Pro enthält Probiotika und Pektine zur Verdauungsunterstützung bei Durchfall",
        "_ingredients_text": "Enterococcus faecium, Pektine, Bentonit, Natriumchlorid, Kaliumchlorid",
    },
    {
        "product_name": "alfavet RodiCare instant",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/rodicare-instant",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Ergänzungsfuttermittel Kleintiere",
        "active_ingredients_raw": "Rohfaser, Kräuter, Vitamine, Mineralstoffe",
        "claimed_benefits_raw": "Päppelfutter für Kaninchen und Meerschweinchen, Nahrungsverweigerung",
        "pack_size": "170 g",
        "price": 14.90,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Instant-Päppelbrei für Kaninchen und Meerschweinchen",
        "_body_text": "RodiCare instant ist ein Päppelfutter für Nager bei Nahrungsverweigerung",
        "_ingredients_text": "Rohfaser, Kräuter, Vitamine, Mineralstoffe, Leinöl",
    },
    {
        "product_name": "alfavet HepatiCare Tabletten",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/hepaticare-tabletten",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Diät-Ergänzungsfuttermittel",
        "active_ingredients_raw": "Mariendistelextrakt (Silymarin), SAMe, Vitamin E, Zink",
        "claimed_benefits_raw": "Leberunterstützung, Leberschutz, Hepatoprotektiv",
        "pack_size": "60 Tabletten",
        "price": 39.90,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Tabletten zur Unterstützung der Leberfunktion bei Hund und Katze",
        "_body_text": "HepatiCare Tabletten enthalten Mariendistel und SAMe für den Leberschutz",
        "_ingredients_text": "Mariendistelextrakt, S-Adenosylmethionin, Vitamin E, Zink",
    },
    {
        "product_name": "alfavet DermaCare Omega Öl",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/dermacare-omega-oel",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Ergänzungsfuttermittel",
        "active_ingredients_raw": "Omega-3-Fettsäuren (EPA, DHA), Omega-6-Fettsäuren, Lachsöl, Biotin",
        "claimed_benefits_raw": "Haut- und Fellpflege, glänzendes Fell, Unterstützung bei Hautproblemen",
        "pack_size": "250 ml",
        "price": 19.90,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Omega-Öl zur Unterstützung von Haut und Fell bei Hunden und Katzen",
        "_body_text": "DermaCare Omega Öl mit EPA und DHA für gesunde Haut und glänzendes Fell",
        "_ingredients_text": "Lachsöl, EPA, DHA, Omega-6-Fettsäuren, Biotin, Vitamin E",
    },
    {
        "product_name": "alfavet UroCare Tabletten",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/urocare-tabletten",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Diät-Ergänzungsfuttermittel",
        "active_ingredients_raw": "Cranberry-Extrakt, D-Mannose, Methionin, Vitamin C",
        "claimed_benefits_raw": "Harnwegsgesundheit, Blasenunterstützung, Harnwegsinfektion-Prophylaxe",
        "pack_size": "60 Tabletten",
        "price": 24.90,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Tabletten zur Unterstützung der Harnwegsgesundheit bei Katzen",
        "_body_text": "UroCare Tabletten mit Cranberry und D-Mannose für die Blasengesundheit",
        "_ingredients_text": "Cranberry-Extrakt, D-Mannose, DL-Methionin, Vitamin C",
    },
    {
        "product_name": "alfavet SeniorCare Pulver",
        "brand": "alfavet",
        "product_url": "https://alfavet.de/produkte/seniorcare-pulver",
        "source_company": "alfavet",
        "source_site": "alfavet.de",
        "category": "Ergänzungsfuttermittel",
        "active_ingredients_raw": "Glucosamin, Chondroitinsulfat, Omega-3, CoQ10, Vitamin E, Selen",
        "claimed_benefits_raw": "Senior-Unterstützung, Gelenkschutz, geistige Fitness älterer Tiere",
        "pack_size": "200 g",
        "price": 34.90,
        "currency": "EUR",
        "availability_status": "in_stock",
        "_description": "Ergänzungsfuttermittel Pulver für ältere Hunde",
        "_body_text": "SeniorCare Pulver unterstützt Gelenke und kognitive Funktion bei Senior-Hunden",
        "_ingredients_text": "Glucosamin, Chondroitinsulfat, Omega-3-Fettsäuren, Coenzym Q10, Vitamin E, Selen",
    },
]

# ---------------------------------------------------------------------------
# Competitor products (Chewy)
# ---------------------------------------------------------------------------
CHEWY_PRODUCTS = [
    {
        "product_name": "Nutramax Cosequin Maximum Strength Joint Health Supplement for Dogs",
        "brand": "Nutramax",
        "product_url": "https://www.chewy.com/nutramax-cosequin-ds-plus-msm",
        "search_term": "dog joint support supplement",
        "price": 38.99,
        "currency": "USD",
        "rating": 4.8,
        "review_count": 12450,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "Glucosamine HCl, Sodium Chondroitin Sulfate, MSM",
        "badges_claims_text": "#1 Veterinarian Recommended Joint Health Supplement",
        "availability": "in_stock",
        "image_url": "https://www.chewy.com/images/nutramax-cosequin.jpg",
        "_search_animal_type": "dog",
        "_search_support_area": "joint_mobility",
    },
    {
        "product_name": "Zesty Paws Mobility Bites Glucosamine Hip & Joint Supplement for Dogs",
        "brand": "Zesty Paws",
        "product_url": "https://www.chewy.com/zesty-paws-mobility-bites",
        "search_term": "dog hip and joint supplement",
        "price": 26.97,
        "currency": "USD",
        "rating": 4.6,
        "review_count": 8930,
        "marketplace_rank_position": 2,
        "active_ingredients_raw": "Glucosamine, Chondroitin, MSM, OptiMSM, Vitamin C, Vitamin E",
        "badges_claims_text": "Autoship Available, Best Seller",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "joint_mobility",
    },
    {
        "product_name": "Purina Pro Plan Veterinary Supplements FortiFlora Probiotic Dog Supplement",
        "brand": "Purina Pro Plan",
        "product_url": "https://www.chewy.com/purina-pro-plan-fortiflora",
        "search_term": "dog probiotic supplement",
        "price": 30.99,
        "currency": "USD",
        "rating": 4.8,
        "review_count": 15200,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "Enterococcus faecium SF68, Vitamins, Minerals",
        "badges_claims_text": "#1 Probiotic Recommended by Veterinarians",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "digestion_gut",
    },
    {
        "product_name": "VetriScience Composure Calming Supplement for Dogs",
        "brand": "VetriScience",
        "product_url": "https://www.chewy.com/vetriscience-composure-calming",
        "search_term": "dog calming supplement",
        "price": 22.49,
        "currency": "USD",
        "rating": 4.4,
        "review_count": 5670,
        "marketplace_rank_position": 3,
        "active_ingredients_raw": "Thiamine (Vitamin B1), L-Theanine, C3 Colostrum Calming Complex",
        "badges_claims_text": "Veterinarian Formulated",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "calming_stress_behavior",
    },
    {
        "product_name": "Zesty Paws Wild Alaskan Salmon Oil for Dogs & Cats",
        "brand": "Zesty Paws",
        "product_url": "https://www.chewy.com/zesty-paws-salmon-oil",
        "search_term": "dog skin and coat supplement",
        "price": 19.97,
        "currency": "USD",
        "rating": 4.7,
        "review_count": 11200,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "Wild Alaskan Salmon Oil, EPA, DHA, Omega-3, Omega-6",
        "badges_claims_text": "Best Seller, Skin & Coat Support",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "skin_coat",
    },
    {
        "product_name": "PetHonesty 10-for-1 Multivitamin with Glucosamine for Dogs",
        "brand": "PetHonesty",
        "product_url": "https://www.chewy.com/pethonesty-10-for-1-multivitamin",
        "search_term": "dog multivitamin supplement",
        "price": 25.99,
        "currency": "USD",
        "rating": 4.6,
        "review_count": 9800,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "Glucosamine, Probiotics, Omega-3, Vitamins A C D E, Biotin",
        "badges_claims_text": "All-in-One Daily Supplement",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "general_wellness",
    },
    {
        "product_name": "Purina Pro Plan Veterinary Supplements FortiFlora Probiotic Cat Supplement",
        "brand": "Purina Pro Plan",
        "product_url": "https://www.chewy.com/purina-pro-plan-fortiflora-cat",
        "search_term": "cat probiotic supplement",
        "price": 30.99,
        "currency": "USD",
        "rating": 4.8,
        "review_count": 9400,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "Enterococcus faecium SF68, Taurine, Vitamins, Minerals",
        "badges_claims_text": "#1 Probiotic Recommended by Veterinarians for Cats",
        "availability": "in_stock",
        "_search_animal_type": "cat",
        "_search_support_area": "digestion_gut",
    },
    {
        "product_name": "Nutramax Denamarin Liver Health Supplement for Dogs",
        "brand": "Nutramax",
        "product_url": "https://www.chewy.com/nutramax-denamarin-liver-health",
        "search_term": "dog liver supplement",
        "price": 44.95,
        "currency": "USD",
        "rating": 4.7,
        "review_count": 4200,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "S-Adenosylmethionine (SAMe), Silybin (Milk Thistle)",
        "badges_claims_text": "#1 Liver Support Brand",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "liver_support",
    },
    {
        "product_name": "Feliway Classic Cat Calming Diffuser Refill",
        "brand": "Feliway",
        "product_url": "https://www.chewy.com/feliway-classic-diffuser-refill",
        "search_term": "cat calming supplement",
        "price": 19.95,
        "currency": "USD",
        "rating": 4.3,
        "review_count": 7800,
        "marketplace_rank_position": 2,
        "active_ingredients_raw": "Feline Facial Pheromone Analogue",
        "badges_claims_text": "#1 Vet Recommended Calming Solution for Cats",
        "availability": "in_stock",
        "_search_animal_type": "cat",
        "_search_support_area": "calming_stress_behavior",
    },
    {
        "product_name": "NaturVet Cranberry Relief Plus Echinacea Soft Chews for Dogs",
        "brand": "NaturVet",
        "product_url": "https://www.chewy.com/naturvet-cranberry-relief",
        "search_term": "dog urinary supplement",
        "price": 16.99,
        "currency": "USD",
        "rating": 4.4,
        "review_count": 3100,
        "marketplace_rank_position": 2,
        "active_ingredients_raw": "Cranberry Extract, Echinacea, Oregon Grape Root, Vitamin C",
        "badges_claims_text": "Urinary Tract Support",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "urinary_renal",
    },
    {
        "product_name": "Zesty Paws Aller-Immune Bites Allergy Supplement for Dogs",
        "brand": "Zesty Paws",
        "product_url": "https://www.chewy.com/zesty-paws-aller-immune",
        "search_term": "dog allergy supplement",
        "price": 26.97,
        "currency": "USD",
        "rating": 4.3,
        "review_count": 6400,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "Colostrum, Apple Cider Vinegar, Probiotics, Salmon Oil, Quercetin",
        "badges_claims_text": "Immune & Allergy Support",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "allergy_sensitivity",
    },
    {
        "product_name": "Nutramax Cosequin Senior Joint Health Supplement for Senior Dogs",
        "brand": "Nutramax",
        "product_url": "https://www.chewy.com/nutramax-cosequin-senior",
        "search_term": "senior dog joint supplement",
        "price": 42.99,
        "currency": "USD",
        "rating": 4.7,
        "review_count": 3800,
        "marketplace_rank_position": 1,
        "active_ingredients_raw": "Glucosamine, Chondroitin, MSM, Omega-3, Boswellia",
        "badges_claims_text": "Specially Formulated for Senior Dogs",
        "availability": "in_stock",
        "_search_animal_type": "dog",
        "_search_support_area": "senior_support",
    },
]


def seed_alfavet_products(session) -> int:
    """Seed alfavet products, classify them, and store with relationships."""
    run = create_source_run(session, "alfavet", "seed")
    count_new = 0

    for raw in ALFAVET_PRODUCTS:
        normalized = normalize_alfavet_product(raw)

        # Extract classification metadata before persisting
        animal_types = normalized.pop("_animal_types", ["unknown"])
        support_areas = normalized.pop("_support_areas", [])
        ingredients_parsed = normalized.pop("_ingredients_parsed", [])
        condition_raw = normalized.pop("_condition_raw", None)

        product, is_new = upsert_product(session, normalized)
        if is_new:
            count_new += 1

        set_product_species(session, product.id, animal_types)
        set_product_support_areas(session, product.id, support_areas, condition_raw)
        if ingredients_parsed:
            set_product_ingredients(session, product.id, ingredients_parsed)

    finish_source_run(
        session, run, "completed",
        products_found=len(ALFAVET_PRODUCTS),
        products_new=count_new,
    )
    return count_new


def seed_chewy_products(session) -> int:
    """Seed Chewy competitor products."""
    run = create_source_run(session, "chewy", "seed")
    count_new = 0

    for raw in CHEWY_PRODUCTS:
        normalized = normalize_chewy_product(raw)
        animal_types = normalized.pop("_animal_types", ["unknown"])
        support_areas = normalized.pop("_support_areas", [])

        cp, is_new = upsert_competitor_product(session, normalized, source_run_id=run.id)
        if is_new:
            count_new += 1

        set_competitor_species(session, cp.id, animal_types)
        set_competitor_support_areas(session, cp.id, support_areas)

    finish_source_run(
        session, run, "completed",
        products_found=len(CHEWY_PRODUCTS),
        products_new=count_new,
    )
    return count_new


def run_seed() -> None:
    """Initialize the database and seed all data."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    init_db()

    session = get_session()
    try:
        alfavet_new = seed_alfavet_products(session)
        logger.info("Seeded %d new alfavet products (of %d total)", alfavet_new, len(ALFAVET_PRODUCTS))

        chewy_new = seed_chewy_products(session)
        logger.info("Seeded %d new Chewy products (of %d total)", chewy_new, len(CHEWY_PRODUCTS))

        session.commit()
        logger.info("Database seeded successfully.")
    except Exception:
        session.rollback()
        logger.exception("Seed failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
