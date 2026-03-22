"""Search term generation for competitor discovery."""

from __future__ import annotations

from taxonomy.support_areas import SUPPORT_AREA_TAXONOMY

ANIMAL_TYPES = [
    "dog",
    "cat",
    "horse",
    "bird",
    "small mammal",
    "reptile",
    "fish",
]

# Consumer-language synonyms per support area
SUPPORT_AREA_SYNONYMS: dict[str, list[str]] = {
    "joint_mobility": ["joint support", "hip and joint", "glucosamine", "mobility"],
    "skin_coat": ["skin and coat", "omega 3", "fish oil", "shedding"],
    "digestion_gut": ["digestive", "probiotic", "prebiotic", "gut health", "fiber"],
    "calming_stress_behavior": ["calming", "anxiety", "stress relief", "calming chews"],
    "immune_support": ["immune support", "immune booster", "antioxidant"],
    "urinary_renal": ["urinary support", "kidney support", "urinary tract"],
    "dental_oral": ["dental", "oral care", "teeth cleaning", "dental chews"],
    "weight_management": ["weight management", "weight control", "low calorie"],
    "allergy_sensitivity": ["allergy support", "allergy relief", "sensitive skin"],
    "senior_support": ["senior support", "senior vitamin", "aging"],
    "puppy_kitten_growth": ["puppy supplement", "kitten supplement", "growth support"],
    "cardiovascular": ["heart support", "cardiovascular", "heart health"],
    "liver_support": ["liver support", "liver health", "hepatic"],
    "cognitive_brain": ["cognitive support", "brain health", "mental sharpness"],
    "eye_vision": ["eye support", "vision health", "eye care"],
    "bone_mineral": ["bone support", "calcium", "mineral supplement"],
    "recovery_convalescence": ["recovery support", "convalescence", "post-surgery"],
    "muscle_performance": ["muscle support", "performance", "stamina"],
    "parasite_repellent_non_drug": ["flea tick natural", "parasite repellent natural"],
    "general_wellness": ["multivitamin", "daily supplement", "general wellness"],
}

# Ingredient-led search terms
INGREDIENT_SEARCHES = [
    "glucosamine chondroitin",
    "fish oil omega 3",
    "probiotics",
    "turmeric curcumin",
    "CBD hemp",
    "collagen",
    "MSM",
    "CoQ10",
    "milk thistle",
    "L-lysine",
    "cranberry",
    "melatonin",
    "biotin",
    "taurine",
    "SAMe",
]


def generate_search_terms(
    animal_types: list[str] | None = None,
    support_areas: list[str] | None = None,
) -> list[dict[str, str]]:
    """Generate search terms for competitor discovery.

    Returns list of dicts with keys: search_term, animal_type, support_area.
    """
    animals = animal_types or ["dog", "cat"]
    areas = support_areas or list(SUPPORT_AREA_SYNONYMS.keys())

    terms: list[dict[str, str]] = []

    for animal in animals:
        for area in areas:
            synonyms = SUPPORT_AREA_SYNONYMS.get(area, [area.replace("_", " ")])
            for synonym in synonyms:
                term = f"{animal} {synonym} supplement"
                terms.append({
                    "search_term": term,
                    "animal_type": animal,
                    "support_area": area,
                })

    # Ingredient-led searches
    for animal in animals:
        for ingredient in INGREDIENT_SEARCHES:
            terms.append({
                "search_term": f"{ingredient} for {animal}s",
                "animal_type": animal,
                "support_area": "general_wellness",
            })

    return terms
