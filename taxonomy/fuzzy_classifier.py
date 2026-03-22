"""Fuzzy taxonomy classifier: improves on the keyword-based classifier with
token-level similarity, German compound word handling, and learning from
manual corrections.

Provides :class:`FuzzyClassifier` which uses Jaccard similarity, partial
matching, and configurable confidence scoring.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from taxonomy.support_areas import SUPPORT_AREA_TAXONOMY

logger = logging.getLogger(__name__)

# Default path for storing manual corrections
_CORRECTIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "manual_corrections.json"

# ---------------------------------------------------------------------------
# German compound-word splitter
# ---------------------------------------------------------------------------

# Common German morphemes that appear as the *second* part of compound words
# related to pet nutraceuticals.
_GERMAN_SPLIT_SUFFIXES: list[str] = [
    "unterstützung",
    "pflege",
    "schutz",
    "stärkung",
    "gesundheit",
    "versorgung",
    "nahrung",
    "ergänzung",
    "mittel",
    "futter",
    "tabletten",
    "kapseln",
    "pulver",
    "tropfen",
    "öl",
]


def split_german_compound(word: str) -> list[str]:
    """Split a German compound word into likely constituent parts.

    Example::

        >>> split_german_compound("Gelenkunterstützung")
        ['Gelenk', 'unterstützung']

    Returns the original word as a single-element list when no split is found.
    """
    word_lower = word.lower()
    for suffix in _GERMAN_SPLIT_SUFFIXES:
        if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 2:
            prefix = word[: len(word) - len(suffix)]
            return [prefix.lower(), suffix]
    return [word_lower]


def tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercased alpha-numeric tokens,
    expanding German compound words where possible."""
    raw_tokens = re.findall(r"[a-zäöüß]+", text.lower())
    expanded: set[str] = set()
    for token in raw_tokens:
        parts = split_german_compound(token)
        expanded.update(parts)
    return expanded


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Return the Jaccard similarity coefficient between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def partial_match_score(text_tokens: set[str], keyword_tokens: set[str]) -> float:
    """Score how many keyword tokens appear as substrings in any text token.

    This catches cases where a keyword token is a prefix/suffix of a longer
    text token (e.g., keyword ``"gelenk"`` matches text token
    ``"gelenkunterstützung"``).
    """
    if not keyword_tokens:
        return 0.0
    hits = 0
    text_joined = " ".join(text_tokens)
    for kw_token in keyword_tokens:
        if kw_token in text_joined:
            hits += 1
    return hits / len(keyword_tokens)


# ---------------------------------------------------------------------------
# FuzzyClassifier
# ---------------------------------------------------------------------------

class FuzzyClassifier:
    """Taxonomy classifier that uses token-level fuzzy matching.

    Improvements over the baseline keyword classifier:

    1. **Jaccard similarity** between product text tokens and area keyword
       tokens — tolerates partial overlap instead of requiring exact
       substrings.
    2. **Partial / substring matching** to handle German compound words
       (e.g., ``Gelenkunterstützung`` matching keyword ``gelenk``).
    3. **Weighted confidence scoring** using keyword density, ingredient
       match ratio, and title vs. description weighting.
    4. **Manual correction learning** — corrections are stored in a JSON
       file and applied as overrides before fuzzy scoring.

    Parameters
    ----------
    corrections_path:
        Path to the JSON file storing manual corrections.  Created
        automatically when corrections are saved.
    title_weight:
        Relative weight for matches found in the product name / title.
    description_weight:
        Relative weight for matches found in the description / claims.
    ingredient_weight:
        Relative weight for matches found in the ingredient list.
    min_score:
        Minimum combined score to include a support area in results.
    """

    def __init__(
        self,
        corrections_path: Path | str | None = None,
        title_weight: float = 0.45,
        description_weight: float = 0.25,
        ingredient_weight: float = 0.30,
        min_score: float = 0.08,
    ) -> None:
        self.corrections_path = Path(corrections_path) if corrections_path else _CORRECTIONS_FILE
        self.title_weight = title_weight
        self.description_weight = description_weight
        self.ingredient_weight = ingredient_weight
        self.min_score = min_score

        # Pre-tokenize taxonomy keywords and ingredient markers
        self._area_keyword_tokens: dict[str, set[str]] = {}
        self._area_ingredient_tokens: dict[str, set[str]] = {}
        for area_key, area_def in SUPPORT_AREA_TAXONOMY.items():
            if area_key in ("other", "unknown"):
                continue
            kw_text = " ".join(area_def.get("keywords", []))
            self._area_keyword_tokens[area_key] = tokenize(kw_text)
            ing_text = " ".join(area_def.get("ingredient_markers", []))
            self._area_ingredient_tokens[area_key] = tokenize(ing_text)

        # Load manual corrections
        self._corrections: dict[str, list[str]] = self._load_corrections()

    # ------------------------------------------------------------------
    # Manual corrections persistence
    # ------------------------------------------------------------------
    def _load_corrections(self) -> dict[str, list[str]]:
        """Load manual corrections from disk.

        Returns a dict mapping ``product_name`` (lowercased) to a list of
        support area keys.
        """
        if self.corrections_path.exists():
            try:
                data = json.loads(self.corrections_path.read_text(encoding="utf-8"))
                logger.info(
                    "Loaded %d manual corrections from %s",
                    len(data),
                    self.corrections_path,
                )
                return {k.lower(): v for k, v in data.items()}
            except Exception as exc:
                logger.warning("Failed to load corrections file: %s", exc)
        return {}

    def save_correction(
        self,
        product_name: str,
        support_areas: list[str],
    ) -> None:
        """Store a manual correction so it is applied in future runs.

        Parameters
        ----------
        product_name:
            The product name to override.
        support_areas:
            List of correct support area keys.
        """
        self._corrections[product_name.lower()] = support_areas
        self.corrections_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.corrections_path.write_text(
                json.dumps(self._corrections, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Saved correction for '%s'", product_name)
        except Exception as exc:
            logger.error("Failed to save correction: %s", exc)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    def _score_area(
        self,
        area_key: str,
        title_tokens: set[str],
        desc_tokens: set[str],
        ingredient_tokens: set[str],
    ) -> float:
        """Compute a combined fuzzy score for a single support area."""
        kw_tokens = self._area_keyword_tokens.get(area_key, set())
        ing_tokens = self._area_ingredient_tokens.get(area_key, set())

        # Title scoring: Jaccard + partial match bonus
        title_jaccard = jaccard_similarity(title_tokens, kw_tokens)
        title_partial = partial_match_score(title_tokens, kw_tokens)
        title_score = max(title_jaccard, title_partial)

        # Description scoring
        desc_jaccard = jaccard_similarity(desc_tokens, kw_tokens)
        desc_partial = partial_match_score(desc_tokens, kw_tokens)
        desc_score = max(desc_jaccard, desc_partial)

        # Ingredient scoring
        ing_jaccard = jaccard_similarity(ingredient_tokens, ing_tokens)
        ing_partial = partial_match_score(ingredient_tokens, ing_tokens)
        ing_score = max(ing_jaccard, ing_partial)

        # Weighted combination
        combined = (
            title_score * self.title_weight
            + desc_score * self.description_weight
            + ing_score * self.ingredient_weight
        )
        return combined

    def classify_with_fuzzy(
        self,
        product_name: str,
        description: str = "",
        ingredients: str = "",
        claims: str = "",
    ) -> list[dict[str, Any]]:
        """Classify a product into support areas using fuzzy token matching.

        Parameters
        ----------
        product_name:
            The product title / name.
        description:
            Product description text.
        ingredients:
            Raw ingredient list text.
        claims:
            Marketing claims / benefits text.

        Returns
        -------
        list[dict]
            Sorted list of dicts with keys ``support_area``, ``score``,
            and ``evidence``.
        """
        # Check manual corrections first
        correction_key = product_name.lower()
        if correction_key in self._corrections:
            corrected_areas = self._corrections[correction_key]
            logger.debug(
                "Using manual correction for '%s': %s",
                product_name,
                corrected_areas,
            )
            return [
                {
                    "support_area": area,
                    "score": 1.0,
                    "evidence": "manual correction",
                }
                for area in corrected_areas
            ]

        # Tokenize inputs
        title_tokens = tokenize(product_name)
        desc_tokens = tokenize(f"{description} {claims}")
        ingredient_tokens = tokenize(ingredients)

        results: list[dict[str, Any]] = []
        for area_key in self._area_keyword_tokens:
            score = self._score_area(
                area_key, title_tokens, desc_tokens, ingredient_tokens
            )
            if score >= self.min_score:
                # Build a brief evidence string
                kw_tokens = self._area_keyword_tokens[area_key]
                matched = (title_tokens | desc_tokens) & kw_tokens
                evidence = ", ".join(sorted(matched)[:5]) if matched else ""

                confidence = min(1.0, score * 2.5)
                results.append(
                    {
                        "support_area": area_key,
                        "score": round(confidence, 3),
                        "evidence": evidence,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)

        if not results:
            results.append(
                {
                    "support_area": "unknown",
                    "score": 0.1,
                    "evidence": "",
                }
            )

        return results
