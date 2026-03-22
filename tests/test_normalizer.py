"""Tests for data normalization and deduplication."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.normalizer import (
    compute_dedup_key,
    normalize_brand,
    normalize_product_name,
    parse_ingredients,
)


class TestNormalizeBrand:
    def test_basic(self):
        assert normalize_brand("AlfaVet") == "alfavet"

    def test_special_chars(self):
        assert normalize_brand("alfa-vet GmbH") == "alfavetgmbh"

    def test_none(self):
        assert normalize_brand(None) == ""


class TestNormalizeProductName:
    def test_basic(self):
        assert normalize_product_name("  Joint Support Plus  ") == "joint support plus"

    def test_trademark(self):
        assert normalize_product_name("Brand® Product™") == "brand product"

    def test_whitespace(self):
        assert normalize_product_name("Multi  Vitamin   Tabs") == "multi vitamin tabs"


class TestParseIngredients:
    def test_comma_separated(self):
        result = parse_ingredients("Glucosamine 500mg, Chondroitin 400mg, MSM 300mg")
        assert len(result) == 3
        assert result[0]["name"] == "Glucosamine 500mg"
        assert "glucosamine" in result[0]["normalized"]

    def test_semicolon_separated(self):
        result = parse_ingredients("Vitamin A; Vitamin B12; Zinc")
        assert len(result) == 3

    def test_empty(self):
        assert parse_ingredients(None) == []
        assert parse_ingredients("") == []

    def test_preserves_raw(self):
        result = parse_ingredients("Omega-3 1000mg, EPA 180mg")
        assert "1000mg" in result[0]["name"]


class TestComputeDedupKey:
    def test_same_product_same_key(self):
        key1 = compute_dedup_key("AlfaVet", "Joint Support", "alfavet")
        key2 = compute_dedup_key("alfavet", "joint support", "alfavet")
        assert key1 == key2

    def test_different_products_different_keys(self):
        key1 = compute_dedup_key("Brand A", "Product 1", "source1")
        key2 = compute_dedup_key("Brand B", "Product 2", "source1")
        assert key1 != key2

    def test_variant_matters(self):
        key1 = compute_dedup_key("Brand", "Product", "src", variant="100g")
        key2 = compute_dedup_key("Brand", "Product", "src", variant="200g")
        assert key1 != key2
