"""Tests for change detection and deduplication logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

from db.crud import compute_content_hash


class TestContentHash:
    def test_deterministic(self):
        data = {"name": "Product A", "price": 19.99}
        assert compute_content_hash(data) == compute_content_hash(data)

    def test_order_independent(self):
        data1 = {"name": "Product A", "price": 19.99}
        data2 = {"price": 19.99, "name": "Product A"}
        assert compute_content_hash(data1) == compute_content_hash(data2)

    def test_change_detected(self):
        data1 = {"name": "Product A", "price": 19.99}
        data2 = {"name": "Product A", "price": 24.99}
        assert compute_content_hash(data1) != compute_content_hash(data2)

    def test_handles_none(self):
        data = {"name": "Product A", "price": None}
        h = compute_content_hash(data)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256
