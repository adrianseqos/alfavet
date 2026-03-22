"""Tests for taxonomy classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.classifier import (
    classify_animal_types,
    classify_form_factor,
    classify_life_stage,
    classify_product,
    classify_support_areas,
)


class TestClassifySupportAreas:
    def test_joint_mobility(self):
        results = classify_support_areas(
            "GelenkFit Plus for Dogs",
            description="Supports joint health and mobility with glucosamine and chondroitin",
            ingredients="glucosamine, chondroitin, MSM, green-lipped mussel",
        )
        areas = [r["support_area"] for r in results]
        assert "joint_mobility" in areas
        assert results[0]["confidence_score"] > 0.3

    def test_skin_coat(self):
        results = classify_support_areas(
            "Omega Skin & Coat Oil",
            description="Promotes healthy skin and shiny coat",
            ingredients="omega-3, omega-6, fish oil, biotin",
        )
        areas = [r["support_area"] for r in results]
        assert "skin_coat" in areas

    def test_digestion(self):
        results = classify_support_areas(
            "ProBiotic Digest",
            description="Supports healthy digestion and gut flora",
            ingredients="probiotic, prebiotic, inulin, fiber",
        )
        areas = [r["support_area"] for r in results]
        assert "digestion_gut" in areas

    def test_calming(self):
        results = classify_support_areas(
            "Calm Tabs",
            description="Helps with stress and anxiety in dogs",
            ingredients="l-theanine, valerian, chamomile, tryptophan",
        )
        areas = [r["support_area"] for r in results]
        assert "calming_stress_behavior" in areas

    def test_unknown_product(self):
        results = classify_support_areas(
            "Product X",
            description="A generic product",
        )
        areas = [r["support_area"] for r in results]
        assert "unknown" in areas

    def test_multi_area(self):
        results = classify_support_areas(
            "Senior Complete",
            description="Joint support and immune health for aging dogs with brain health benefits",
            ingredients="glucosamine, vitamin c, DHA, omega-3",
        )
        areas = [r["support_area"] for r in results]
        assert len(areas) >= 2

    def test_german_keywords(self):
        results = classify_support_areas(
            "Gelenk Aktiv Pulver",
            description="Unterstützt die Gelenkgesundheit und Beweglichkeit",
            ingredients="Grünlippmuschel, Kollagen",
        )
        areas = [r["support_area"] for r in results]
        assert "joint_mobility" in areas

    def test_evidence_snippet_present(self):
        results = classify_support_areas(
            "Joint Support for Dogs",
            description="Glucosamine and chondroitin for hip and joint mobility",
            ingredients="glucosamine, chondroitin",
        )
        assert results[0]["evidence_snippet"]


class TestClassifyAnimalTypes:
    def test_dog(self):
        assert "dog" in classify_animal_types("Dog Joint Supplement")

    def test_cat(self):
        assert "cat" in classify_animal_types("Katzen Ergänzung", category="Katze")

    def test_horse(self):
        assert "horse" in classify_animal_types("Equine Joint Care", category="Pferde")

    def test_multi_species(self):
        result = classify_animal_types(
            "Universal Pet Supplement",
            description="For dogs, cats, and horses",
        )
        assert "multi-species" in result

    def test_unknown(self):
        result = classify_animal_types("Product X")
        assert "unknown" in result

    def test_german_dog(self):
        assert "dog" in classify_animal_types("Hunde Gelenk Fit")


class TestClassifyLifeStage:
    def test_puppy(self):
        assert classify_life_stage("Puppy Growth Formula") == "puppy"

    def test_senior(self):
        assert classify_life_stage("Senior Dog Vitamins") == "senior"

    def test_none(self):
        assert classify_life_stage("Regular Supplement") is None

    def test_german_welpe(self):
        assert classify_life_stage("Welpen Starter") == "puppy"


class TestClassifyFormFactor:
    def test_powder(self):
        assert classify_form_factor("Joint Support Powder") == "powder"

    def test_tablet(self):
        assert classify_form_factor("Vitamin Tabletten") == "tablet"

    def test_liquid(self):
        assert classify_form_factor("Flüssiges Ergänzungsmittel") == "liquid"

    def test_chew(self):
        assert classify_form_factor("Calming Chews for Dogs") == "chew"

    def test_none(self):
        assert classify_form_factor("Regular Product") is None


class TestClassifyProduct:
    def test_full_classification(self):
        result = classify_product(
            product_name="Senior Dog Joint Chews",
            description="Supports hip and joint health in senior dogs",
            ingredients="glucosamine, chondroitin, omega-3",
            claims="Promotes mobility and flexibility",
            category="Hunde",
        )
        assert "dog" in result.animal_types
        assert result.life_stage == "senior"
        assert result.form_factor == "chew"
        areas = [a["support_area"] for a in result.support_areas]
        assert "joint_mobility" in areas
