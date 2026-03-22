"""Standardized support area taxonomy for pet nutraceutical classification."""

from __future__ import annotations

SUPPORT_AREA_TAXONOMY: dict[str, dict] = {
    "joint_mobility": {
        "label": "Joint & Mobility Support",
        "keywords": [
            "joint", "mobility", "hip", "glucosamine", "chondroitin", "msm",
            "arthritis", "gelenk", "bewegung", "beweglichkeit", "hüfte",
            "gelenkschutz", "gelenkunterstützung",
        ],
        "ingredient_markers": [
            "glucosamine", "chondroitin", "msm", "hyaluronic acid", "green-lipped mussel",
            "grünlippmuschel", "kollagen", "collagen", "omega-3",
        ],
    },
    "skin_coat": {
        "label": "Skin & Coat Support",
        "keywords": [
            "skin", "coat", "fur", "shedding", "omega", "fell", "haut",
            "fellpflege", "hautpflege", "glänzendes fell",
        ],
        "ingredient_markers": [
            "omega-3", "omega-6", "fish oil", "biotin", "zinc", "fischöl",
            "leinöl", "lachsöl", "nachtkerzenöl",
        ],
    },
    "digestion_gut": {
        "label": "Digestive & Gut Support",
        "keywords": [
            "digest", "probiotic", "prebiotic", "gut", "stomach", "intestin",
            "verdauung", "darm", "magen", "probiotik", "prebiotik",
        ],
        "ingredient_markers": [
            "probiotic", "prebiotic", "fiber", "fos", "inulin", "pumpkin",
            "psyllium", "enterococcus", "lactobacillus",
        ],
    },
    "calming_stress_behavior": {
        "label": "Calming & Stress Support",
        "keywords": [
            "calm", "stress", "anxiety", "relax", "behavior", "beruhigung",
            "stress", "angst", "entspannung", "nervös",
        ],
        "ingredient_markers": [
            "l-theanine", "valerian", "chamomile", "tryptophan", "melatonin",
            "gaba", "passionflower", "baldrian", "kamille",
        ],
    },
    "immune_support": {
        "label": "Immune Support",
        "keywords": [
            "immune", "immunity", "antioxidant", "immunsystem", "abwehr",
            "immunstärkung", "widerstandskraft",
        ],
        "ingredient_markers": [
            "vitamin c", "vitamin e", "beta-glucan", "echinacea", "colostrum",
            "zinc", "selenium", "astragalus",
        ],
    },
    "urinary_renal": {
        "label": "Urinary & Renal Support",
        "keywords": [
            "urinary", "kidney", "renal", "bladder", "uti", "harnweg",
            "niere", "blase", "harnwegsinfektion",
        ],
        "ingredient_markers": [
            "cranberry", "d-mannose", "methionine", "potassium citrate",
        ],
    },
    "dental_oral": {
        "label": "Dental & Oral Care",
        "keywords": [
            "dental", "oral", "teeth", "gum", "plaque", "tartar", "zahn",
            "zahnpflege", "mundpflege", "zahnstein",
        ],
        "ingredient_markers": [
            "chlorhexidine", "sodium hexametaphosphate", "zinc ascorbate",
        ],
    },
    "weight_management": {
        "label": "Weight Management",
        "keywords": [
            "weight", "obesity", "diet", "low calorie", "gewicht",
            "gewichtsmanagement", "diät", "übergewicht",
        ],
        "ingredient_markers": [
            "l-carnitine", "conjugated linoleic acid", "fiber", "chromium",
        ],
    },
    "allergy_sensitivity": {
        "label": "Allergy & Sensitivity Support",
        "keywords": [
            "allergy", "allergies", "sensitive", "itch", "allergie",
            "empfindlich", "juckreiz", "unverträglichkeit",
        ],
        "ingredient_markers": [
            "quercetin", "bromelain", "colostrum", "omega-3",
        ],
    },
    "senior_support": {
        "label": "Senior Support",
        "keywords": [
            "senior", "aging", "elderly", "old", "senior", "alter",
            "ältere tiere",
        ],
        "ingredient_markers": [
            "glucosamine", "omega-3", "antioxidant", "coq10", "sam-e",
        ],
    },
    "puppy_kitten_growth": {
        "label": "Puppy/Kitten Growth Support",
        "keywords": [
            "puppy", "kitten", "growth", "young", "junior", "welpe",
            "kitten", "wachstum", "junior",
        ],
        "ingredient_markers": [
            "dha", "calcium", "phosphorus", "colostrum",
        ],
    },
    "cardiovascular": {
        "label": "Cardiovascular Support",
        "keywords": [
            "heart", "cardiovascular", "cardiac", "herz", "kardio",
            "herzunterstützung",
        ],
        "ingredient_markers": [
            "taurine", "coq10", "omega-3", "l-carnitine", "hawthorn",
        ],
    },
    "liver_support": {
        "label": "Liver Support",
        "keywords": [
            "liver", "hepatic", "leber", "leberschutz", "hepato",
        ],
        "ingredient_markers": [
            "milk thistle", "sam-e", "silybin", "silymarin", "artichoke",
            "mariendistel",
        ],
    },
    "cognitive_brain": {
        "label": "Cognitive & Brain Support",
        "keywords": [
            "cognitive", "brain", "mental", "dementia", "gehirn", "kognitiv",
            "geistige fitness",
        ],
        "ingredient_markers": [
            "dha", "mct oil", "phosphatidylserine", "ginkgo", "vitamin e",
        ],
    },
    "eye_vision": {
        "label": "Eye & Vision Support",
        "keywords": [
            "eye", "vision", "sight", "auge", "sehkraft", "augenpflege",
        ],
        "ingredient_markers": [
            "lutein", "zeaxanthin", "bilberry", "vitamin a", "astaxanthin",
        ],
    },
    "bone_mineral": {
        "label": "Bone & Mineral Support",
        "keywords": [
            "bone", "mineral", "calcium", "knochen", "mineral",
            "knochenstärkung",
        ],
        "ingredient_markers": [
            "calcium", "phosphorus", "vitamin d", "magnesium",
        ],
    },
    "recovery_convalescence": {
        "label": "Recovery & Convalescence",
        "keywords": [
            "recovery", "convalescence", "post-surgery", "healing",
            "erholung", "rekonvaleszenz", "genesung",
        ],
        "ingredient_markers": [
            "glutamine", "arginine", "zinc", "vitamin c", "iron",
        ],
    },
    "muscle_performance": {
        "label": "Muscle & Performance Support",
        "keywords": [
            "muscle", "performance", "stamina", "energy", "muskel",
            "leistung", "ausdauer", "energie",
        ],
        "ingredient_markers": [
            "creatine", "bcaa", "l-carnitine", "coq10", "iron",
        ],
    },
    "parasite_repellent_non_drug": {
        "label": "Natural Parasite Repellent (Non-Drug)",
        "keywords": [
            "flea", "tick", "parasite", "repel", "natural", "floh", "zecke",
            "parasit", "natürlich", "abwehr",
        ],
        "ingredient_markers": [
            "neem", "citronella", "geraniol", "coconut oil", "garlic",
            "brewer's yeast", "bierhefe",
        ],
    },
    "general_wellness": {
        "label": "General Wellness",
        "keywords": [
            "wellness", "multivitamin", "daily", "general", "health",
            "allgemein", "gesundheit", "vitamine", "nahrungsergänzung",
        ],
        "ingredient_markers": [
            "multivitamin", "vitamin b complex", "mineral mix",
        ],
    },
    "other": {
        "label": "Other",
        "keywords": [],
        "ingredient_markers": [],
    },
    "unknown": {
        "label": "Unknown",
        "keywords": [],
        "ingredient_markers": [],
    },
}

ANIMAL_TYPES = [
    "dog", "cat", "horse", "bird", "small mammal",
    "reptile", "fish", "multi-species", "unknown",
]

ANIMAL_TYPE_KEYWORDS: dict[str, list[str]] = {
    "dog": ["dog", "hund", "hunde", "canine", "puppy", "welpe"],
    "cat": ["cat", "katze", "katzen", "feline", "kitten", "kätzchen"],
    "horse": ["horse", "pferd", "pferde", "equine", "pony", "fohlen"],
    "bird": ["bird", "vogel", "vögel", "avian", "parrot", "papagei"],
    "small mammal": [
        "rabbit", "kaninchen", "hamster", "guinea pig", "meerschweinchen",
        "ferret", "frettchen", "chinchilla", "gerbil", "rennmaus",
        "kleintier", "nager",
    ],
    "reptile": [
        "reptile", "reptil", "reptilien", "turtle", "schildkröte",
        "lizard", "eidechse", "snake", "schlange",
    ],
    "fish": ["fish", "fisch", "fische", "aquarium", "aquaristik"],
}

LIFE_STAGES = ["puppy", "kitten", "junior", "adult", "senior", "all_ages"]

FORM_FACTORS = [
    "powder", "chew", "tablet", "capsule", "liquid", "paste",
    "treat", "gel", "spray", "oil", "granule", "drop", "injection",
    "cream", "ointment", "shampoo",
]
