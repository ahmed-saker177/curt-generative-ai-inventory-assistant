"""
phase1_assistant.py

CURT Inventory Assistant - Phase 1
Deterministic, rule-based assistant without AI model dependencies.

Maps natural language questions to 8 structured inventory intents:
    1. Check quantity
    2. Find location
    3. List items by category
    4. Check item existence / availability
    5. Show all inventory
    6. Find low-stock items
    7. Count items in a category
    8. Show available categories

Database remains the source of truth.
"""

import difflib
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.app.data.db import (
    get_all_categories,
    get_all_locations,
    get_all_part_names,
    get_all_parts,
    get_by_category,
    get_by_location,
    get_part,
)


# ============================================================
# CONSTANTS & CONFIGURATION
# ============================================================

INTENT_QUANTITY = "quantity"
INTENT_LOCATION = "location"
INTENT_CATEGORY_LIST = "category_list"
INTENT_EXISTS = "exists"
INTENT_ALL_INVENTORY = "all_inventory"
INTENT_LOW_STOCK = "low_stock"
INTENT_CATEGORY_COUNT = "category_count"
INTENT_CATEGORIES = "categories"
INTENT_LOCATION_LIST = "location_list"
INTENT_LOCATIONS = "locations"
INTENT_UNKNOWN = "unknown"

DEFAULT_LOW_STOCK_THRESHOLD = 5

FALLBACK_MSG = """
Sorry, I couldn't understand that inventory question.

I can help with things like:

• How many brake pads do we have?
• Where is the ECU?
• Where are the brake pads stored?
• What do we have in Mechanical Workshop?
• List all items in Brakes.
• Show me everything in Electronics.
• Do we have an ECU?
• Is the ECU available?
• Show me the inventory.
• Which items are low in stock?
• How many items are in the Engine category?
• What categories do we have?
• What locations do we have?

Try asking one of these types of questions.
""".strip()

WORD_SYNONYMS = {
    # quantity
    "qty": "quantity",
    "amount": "quantity",
    "count": "quantity",
    "number": "quantity",
    "stock": "quantity",
    "available": "quantity",
    # location
    "stored": "location",
    "kept": "location",
    "located": "location",
    "place": "location",
    # inventory
    "parts": "items",
    "part": "item",
}

QUANTITY_PATTERNS = [
    "how many",
    "how much",
    "quantity",
    "how many do we have",
    "how many are there",
    "how many left",
    "how many are left",
    "in stock",
    "available",
    "stock level",
    "stock",
]

LOCATION_PATTERNS = [
    "where",
    "where is",
    "where are",
    "where can i find",
    "where do i find",
    "location",
    "stored",
    "kept",
    "located",
]

CATEGORY_LIST_PATTERNS = [
    "list",
    "show",
    "what",
    "which",
]

EXISTENCE_PATTERNS = [
    "do we have",
    "does the inventory have",
    "is there",
    "are there",
    "do you have",
    "is available",
    "are available",
    "available",
]

ALL_INVENTORY_PATTERNS = [
    "show inventory",
    "show all inventory",
    "show all items",
    "list all inventory",
    "list all items",
    "what do we have",
    "what items do we have",
    "everything in inventory",
    "all inventory",
]

LOW_STOCK_PATTERNS = [
    "low stock",
    "low in stock",
    "low on stock",
    "low quantity",
    "low in quantity",
    "running low",
    "almost out",
    "running out",
    "shortage",
    "shortages",
    "items are low",
    "items low",
    "parts are low",
    "parts low",
    "which items are low",
    "what items are low",
    "which parts are low",
    "what parts are low",
    "low inventory",
]

CATEGORY_COUNT_PATTERNS = [
    "how many items in",
    "how many parts in",
    "count items in",
    "count parts in",
    "number of items in",
    "number of parts in",
]

CATEGORIES_PATTERNS = [
    "what categories",
    "which categories",
    "list categories",
    "show categories",
    "categories do we have",
]

LOCATION_LIST_PATTERNS = [
    "what do we have in",
    "what is in",
    "what is stored in",
    "what is kept in",
    "what are in",
    "what parts are in",
    "what items are in",
    "list items in",
    "list parts in",
    "show items in",
    "show parts in",
    "show everything in",
]

LOCATIONS_PATTERNS = [
    "what locations",
    "which locations",
    "list locations",
    "show locations",
    "locations do we have",
    "storage locations",
    "where are items stored",
]


# ============================================================
# TEXT NORMALIZATION & TOKENIZATION
# ============================================================

def _normalize(text: str) -> str:
    """Lowercase text and strip non-alphanumeric characters and extra spaces."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokens(text: str) -> List[str]:
    """Tokenize normalized text into words."""
    return _normalize(text).split()


def _normalize_synonyms(text: str) -> str:
    """Replace known deterministic synonyms."""
    words = _tokens(text)
    normalized = [WORD_SYNONYMS.get(word, word) for word in words]
    return " ".join(normalized)


def _contains_phrase(text: str, phrases: List[str]) -> bool:
    """Check if any phrase is a substring of text."""
    return any(phrase in text for phrase in phrases)


def _contains_any_word(text: str, words: List[str]) -> bool:
    """Check if any word exists in text tokens."""
    tokens = set(_tokens(text))
    return any(word in tokens for word in words)


# ============================================================
# INTENT DETECTION
# ============================================================

def detect_intent(raw_text: str) -> str:
    """Determine the most likely intent using deterministic scoring rules."""
    text = _normalize_synonyms(raw_text)
    clean_raw = _normalize(raw_text)
    if not text:
        return INTENT_UNKNOWN

    scores = {
        INTENT_QUANTITY: 0,
        INTENT_LOCATION: 0,
        INTENT_CATEGORY_LIST: 0,
        INTENT_EXISTS: 0,
        INTENT_ALL_INVENTORY: 0,
        INTENT_LOW_STOCK: 0,
        INTENT_CATEGORY_COUNT: 0,
        INTENT_CATEGORIES: 0,
        INTENT_LOCATION_LIST: 0,
        INTENT_LOCATIONS: 0,
    }

    # All Inventory (+5) - only when not scoped by 'in <category/location>'
    has_in_qualifier = " in " in clean_raw or clean_raw.endswith(" in") or "items in" in clean_raw or "parts in" in clean_raw
    if not has_in_qualifier:
        for pattern in ALL_INVENTORY_PATTERNS:
            if pattern in text:
                scores[INTENT_ALL_INVENTORY] += 5
    else:
        if any(marker in text for marker in ["list", "show", "items", "parts"]):
            scores[INTENT_CATEGORY_LIST] += 5

    # Low Stock (+6)
    for pattern in LOW_STOCK_PATTERNS:
        if pattern in clean_raw or pattern in text:
            scores[INTENT_LOW_STOCK] += 6

    # Strong low stock indicators
    if "low" in clean_raw.split() and any(w in clean_raw.split() for w in ["stock", "quantity", "inventory"]):
        scores[INTENT_LOW_STOCK] += 6

    # Category Count (+7)
    for pattern in CATEGORY_COUNT_PATTERNS:
        if pattern in text:
            scores[INTENT_CATEGORY_COUNT] += 7
            scores[INTENT_QUANTITY] -= 6

    # Categories (+5)
    for pattern in CATEGORIES_PATTERNS:
        if pattern in text:
            scores[INTENT_CATEGORIES] += 5

    # Locations (+5)
    for pattern in LOCATIONS_PATTERNS:
        if pattern in text or pattern in clean_raw:
            scores[INTENT_LOCATIONS] += 5

    # Location List (+4)
    for pattern in LOCATION_LIST_PATTERNS:
        if pattern in clean_raw:
            scores[INTENT_LOCATION_LIST] += 4

    # Strong location list indicators
    if "what do we have in" in clean_raw:
        scores[INTENT_LOCATION_LIST] += 6
        scores[INTENT_ALL_INVENTORY] -= 5

    # Check if an actual location is mentioned (avoid matching standalone category words like "electronics")
    known_locations = get_all_locations()
    location_keywords = ["workshop", "lab", "shelf", "composites room", "storage room", "engine bay", "rack", "cockpit storage"]
    has_location_mention = any(loc.lower() in clean_raw for loc in known_locations) or any(
        loc_kw in clean_raw for loc_kw in location_keywords
    )

    if has_location_mention and ("in" in clean_raw.split() or "stored" in clean_raw or "at" in clean_raw.split() or "what" in clean_raw.split()):
        scores[INTENT_LOCATION_LIST] += 7
        scores[INTENT_ALL_INVENTORY] -= 5
        scores[INTENT_CATEGORY_LIST] -= 5

    # Quantity (+3 for patterns, +5 for strong indicators)
    for pattern in QUANTITY_PATTERNS:
        if pattern in text:
            scores[INTENT_QUANTITY] += 3
    if "how many" in text:
        scores[INTENT_QUANTITY] += 5
    if "how much" in text:
        scores[INTENT_QUANTITY] += 5

    # Location (+3 for patterns, +5 for startswith)
    for pattern in LOCATION_PATTERNS:
        if pattern in text:
            scores[INTENT_LOCATION] += 3
    if text.startswith("where"):
        scores[INTENT_LOCATION] += 5

    # Existence (+2 for patterns)
    for pattern in EXISTENCE_PATTERNS:
        if pattern in text:
            scores[INTENT_EXISTS] += 2

    # Category List (+1 for patterns, +3/+4 for specific indicators)
    for pattern in CATEGORY_LIST_PATTERNS:
        if pattern in text:
            scores[INTENT_CATEGORY_LIST] += 1
    if "category" in text:
        scores[INTENT_CATEGORY_LIST] += 4

    known_categories = get_all_categories()
    category_query_markers = ("list", "show", "items", "parts", "everything")
    has_category_mention = any(
        re.search(rf"\b{re.escape(category.lower())}\b", clean_raw)
        for category in known_categories
    )
    if has_category_mention and any(marker in text for marker in category_query_markers):
        scores[INTENT_CATEGORY_LIST] += 8
        scores[INTENT_ALL_INVENTORY] -= 5

    # Special Case: "do we have X?" prioritizes existence over quantity
    if "do we have" in text:
        scores[INTENT_EXISTS] += 5
        if "how many" not in text:
            scores[INTENT_QUANTITY] -= 3

    # Special Case: low stock questions should not be swallowed by general quantity intent
    if scores[INTENT_LOW_STOCK] > 0 and "how many" not in text and "how much" not in text:
        scores[INTENT_QUANTITY] -= 8

    best_intent = max(scores, key=scores.get)
    if scores[best_intent] <= 0:
        return INTENT_UNKNOWN

    return best_intent


# ============================================================
# FUZZY ENTITY MATCHING & EXTRACTION
# ============================================================

def _closest_item_match(query: str, cutoff: float = 0.55) -> Optional[str]:
    """
    Match query string to known inventory item names.
    Applies exact, partial, fuzzy whole-string, and word-level fuzzy matching.
    """
    query = _normalize(query)
    if not query:
        return None

    names = get_all_part_names()
    if not names:
        return None

    lowered = {name.lower(): name for name in names}

    # 1. Exact match
    if query in lowered:
        return lowered[query]

    # 2. Substring / partial match
    partial_matches = [
        name for name in names
        if query in name.lower() or name.lower() in query
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]

    # 3. Fuzzy whole-string matching
    matches = difflib.get_close_matches(query, lowered.keys(), n=3, cutoff=cutoff)
    if matches:
        return lowered[matches[0]]

    # 4. Word-level fuzzy matching
    query_words = query.split()
    candidate_scores = []

    for name in names:
        name_words = name.lower().split()
        matched_words = 0
        for query_word in query_words:
            close = difflib.get_close_matches(query_word, name_words, n=1, cutoff=0.65)
            if close:
                matched_words += 1
        if matched_words:
            score = matched_words / max(len(query_words), 1)
            candidate_scores.append((score, name))

    if candidate_scores:
        candidate_scores.sort(reverse=True)
        best_score, best_name = candidate_scores[0]
        if best_score >= 0.5:
            return best_name

    return None


def _extract_item(text: str, intent: str = "") -> str:
    """Remove boilerplate question phrases to isolate candidate item name."""
    t = _normalize(text)
    removal_patterns = [
        # Quantity
        r"\bhow many\b",
        r"\bhow much\b",
        r"\bdo we have\b",
        r"\bdoes the inventory have\b",
        r"\bare there\b",
        r"\bin stock\b",
        r"\bavailable\b",
        r"\bcurrently\b",
        r"\bright now\b",
        r"\bare left\b",
        r"\bleft\b",
        r"\binventory\b",
        r"\bquantity\b",
        r"\bcount\b",
        r"\bnumber of\b",
        # Location
        r"\bwhere is\b",
        r"\bwhere are\b",
        r"\bwhere can i find\b",
        r"\bwhere do i find\b",
        r"\bwhere\b",
        r"\bcan i find\b",
        r"\bstored\b",
        r"\bkept\b",
        r"\blocated\b",
        r"\blocation\b",
        # Existence
        r"\bis there\b",
        r"\bdo you have\b",
        r"\bdoes the inventory have\b",
        # Filler
        r"\bplease\b",
        r"\bcan you\b",
        r"\bcould you\b",
        r"\btell me\b",
        r"\bshow me\b",
        r"\bthe\b",
        r"\ba\b",
        r"\ban\b",
    ]

    for pattern in removal_patterns:
        t = re.sub(pattern, " ", t)

    return re.sub(r"\s+", " ", t).strip()


def _extract_category(text: str) -> str:
    """Remove boilerplate question phrases to isolate candidate category name."""
    t = _normalize(text)
    patterns = [
        r"\blist all items in\b",
        r"\blist items in\b",
        r"\blist all\b",
        r"\blist\b",
        r"\bshow all items in\b",
        r"\bshow items in\b",
        r"\bshow everything in\b",
        r"\bshow\b",
        r"\bwhat parts are in\b",
        r"\bwhat items are in\b",
        r"\bitems in\b",
        r"\bparts in\b",
        r"\bcategory\b",
        r"\bthe\b",
        r"\bplease\b",
    ]

    for pattern in patterns:
        t = re.sub(pattern, " ", t)

    return re.sub(r"\s+", " ", t).strip()


def _closest_category_match(query: str) -> Optional[str]:
    """Match query to valid inventory categories via exact, fuzzy, or substring search."""
    query = _normalize(query)
    if not query:
        return None

    categories = get_all_categories()
    if not categories:
        return None

    lowered = {cat.lower(): cat for cat in categories}
    if query in lowered:
        return lowered[query]

    matches = difflib.get_close_matches(query, lowered.keys(), n=1, cutoff=0.55)
    if matches:
        return lowered[matches[0]]

    for cat in categories:
        if query in cat.lower():
            return cat

    return query


def _extract_location(text: str) -> str:
    """Remove boilerplate question phrases to isolate candidate location name."""
    t = _normalize(text)
    patterns = [
        r"\bwhat do we have in\b",
        r"\bwhat do we have\b",
        r"\bwhat is stored in\b",
        r"\bwhat is kept in\b",
        r"\bwhat is in\b",
        r"\bwhat are in\b",
        r"\bwhat parts are in\b",
        r"\bwhat items are in\b",
        r"\blist all items in\b",
        r"\blist items in\b",
        r"\blist all in\b",
        r"\blist in\b",
        r"\blist\b",
        r"\bshow all items in\b",
        r"\bshow items in\b",
        r"\bshow everything in\b",
        r"\bshow in\b",
        r"\bshow\b",
        r"\bitems in\b",
        r"\bparts in\b",
        r"\bstored in\b",
        r"\bkept in\b",
        r"\blocated in\b",
        r"\blocation\b",
        r"\bin\b",
        r"\bat\b",
        r"\bthe\b",
        r"\bplease\b",
    ]
    for pattern in patterns:
        t = re.sub(pattern, " ", t)

    return re.sub(r"\s+", " ", t).strip()


def _closest_location_match(query: str) -> Optional[str]:
    """Match query to valid inventory storage locations via exact, substring, or fuzzy search."""
    query = _normalize(query)
    if not query:
        return None

    locations = get_all_locations()
    if not locations:
        return None

    lowered = {loc.lower(): loc for loc in locations}
    if query in lowered:
        return lowered[query]

    # Check if query is a broader location matching multiple shelves (e.g. "Electronics Lab")
    substring_matches = [loc for loc in locations if query in loc.lower()]
    if len(substring_matches) > 1:
        return query.title()

    if len(substring_matches) == 1:
        return substring_matches[0]

    for loc in locations:
        if loc.lower() in query:
            return loc

    matches = difflib.get_close_matches(query, lowered.keys(), n=1, cutoff=0.55)
    if matches:
        return lowered[matches[0]]

    # Word-level intersection
    query_words = set(query.split())
    for loc in locations:
        loc_words = set(loc.lower().split())
        common = {w for w in query_words.intersection(loc_words) if len(w) > 3}
        if common:
            return loc

    return query


def _format_items(items: List[Dict[str, Any]]) -> str:
    """Format a list of inventory item records into readable markdown bullet points."""
    if not items:
        return "No items found."
    return "\n".join(
        f"- {item['name']} (qty: {item['quantity']}, category: {item['category']}, location: {item['location']})"
        for item in items
    )


# ============================================================
# INTENT HANDLERS
# ============================================================

def _handle_quantity(text: str) -> Tuple[str, List[str]]:
    item_query = _extract_item(text, INTENT_QUANTITY)
    if not item_query:
        return (
            'Which item do you mean? For example: "How many brake pads do we have?"',
            ["How many brake pads do we have?", "Where is the ECU?"],
        )

    item_name = _closest_item_match(item_query)
    if not item_name:
        return (
            f'I couldn\'t find an inventory item matching "{item_query}".',
            ["Show all inventory.", "What categories do we have?"],
        )

    part = get_part(item_name)
    if not part:
        return (
            f'I found "{item_name}", but could not retrieve its inventory information.',
            ["Show all inventory."],
        )

    return (
        f"We have {part['quantity']} {part['name']} in stock.",
        [f"Where is {part['name']} stored?", f"List all items in {part['category']}."],
    )


def _handle_location(text: str) -> Tuple[str, List[str]]:
    item_query = _extract_item(text, INTENT_LOCATION)
    if not item_query:
        return (
            "Which item's location are you asking about?",
            ["Where is the ECU?", "Where are the brake pads stored?"],
        )

    item_name = _closest_item_match(item_query)
    if not item_name:
        return (
            f'I couldn\'t find an inventory item matching "{item_query}".',
            ["Show all inventory.", "What categories do we have?"],
        )

    part = get_part(item_name)
    if not part:
        return (
            f'I found "{item_name}", but could not retrieve its location.',
            ["Show all inventory."],
        )

    return (
        f"{part['name']} is stored in {part['location']}.",
        [f"How many {part['name']} do we have?", f"List all items in {part['category']}."],
    )


def _handle_category_list(text: str) -> Tuple[str, List[str]]:
    category_query = _extract_category(text)
    if not category_query:
        return (
            "Which category would you like to list?",
            ["What categories do we have?", "Show me everything in Electronics."],
        )

    category = _closest_category_match(category_query)
    if not category:
        return (
            f'No category matching "{category_query}" was found.',
            ["What categories do we have?", "Show all inventory."],
        )

    items = get_by_category(category)
    if not items:
        return (
            f'No items found in category "{category}".',
            ["What categories do we have?", "Show all inventory."],
        )

    first_item = items[0]["name"]
    return (
        f'Items in category "{category}":\n' + _format_items(items),
        [
            f"How many items are in {category}?",
            f"Where is {first_item} stored?",
            f"How many {first_item} do we have?",
        ],
    )


def _handle_exists(text: str) -> Tuple[str, List[str]]:
    item_query = _extract_item(text, INTENT_EXISTS)
    if not item_query:
        return (
            "Which item would you like me to check?",
            ["Do we have an ECU?", "Is the Steering Wheel available?"],
        )

    item_name = _closest_item_match(item_query)
    if not item_name:
        return (
            f'No inventory item matching "{item_query}" was found.',
            ["Show all inventory.", "What categories do we have?"],
        )

    part = get_part(item_name)
    if not part:
        return (
            f'No, I could not find "{item_query}" in the inventory.',
            ["Show all inventory."],
        )

    if part["quantity"] > 0:
        return (
            f"Yes. We have {part['quantity']} {part['name']} in stock.",
            [f"Where is {part['name']} stored?", f"List all items in {part['category']}."],
        )

    return (
        f"Yes, {part['name']} exists in the inventory, but its current quantity is 0.",
        [f"Where is {part['name']} stored?", "Which items are low in stock?"],
    )


def _handle_all_inventory(text: str = "") -> Tuple[str, List[str]]:
    items = get_all_parts()
    if not items:
        return ("The inventory is currently empty.", ["What categories do we have?"])

    return (
        "Current inventory:\n" + _format_items(items),
        [
            "Which items are low in stock?",
            "What categories do we have?",
            "Where is the ECU stored?",
        ],
    )


def _handle_low_stock(text: str = "") -> Tuple[str, List[str]]:
    items = get_all_parts()
    low_stock = [item for item in items if item["quantity"] <= DEFAULT_LOW_STOCK_THRESHOLD]
    if not low_stock:
        return (
            f"There are currently no items at or below the low-stock threshold of {DEFAULT_LOW_STOCK_THRESHOLD}.",
            ["Show all inventory.", "What categories do we have?"],
        )

    first_item = low_stock[0]["name"]
    return (
        f"Low-stock items (quantity <= {DEFAULT_LOW_STOCK_THRESHOLD}):\n" + _format_items(low_stock),
        [f"Where is {first_item} stored?", f"How many {first_item} do we have?"],
    )


def _handle_category_count(text: str) -> Tuple[str, List[str]]:
    category_query = _extract_category(text)
    if not category_query:
        return (
            "Which category would you like me to count?",
            ["What categories do we have?", "How many items are in the Electronics category?"],
        )

    category = _closest_category_match(category_query)
    if not category:
        return (
            f'No category matching "{category_query}" was found.',
            ["What categories do we have?", "Show all inventory."],
        )

    items = get_by_category(category)
    if not items:
        return (
            f'No items found in category "{category}".',
            ["What categories do we have?", "Show all inventory."],
        )

    return (
        f'There are {len(items)} different item types in the "{category}" category.',
        [f"List all items in {category}.", "What categories do we have?"],
    )


def _handle_categories(text: str = "") -> Tuple[str, List[str]]:
    categories = get_all_categories()
    if not categories:
        return ("There are currently no categories.", ["Show all inventory."])

    categories = sorted(set(categories))
    return (
        "Available categories:\n" + "\n".join(f"- {category}" for category in categories),
        [
            "List all items in Brakes.",
            "Show me everything in Electronics.",
            "What locations do we have?",
        ],
    )


def _handle_location_list(text: str) -> Tuple[str, List[str]]:
    location_query = _extract_location(text)
    if not location_query:
        return (
            "Which location would you like to check?",
            [
                "What do we have in Mechanical Workshop?",
                "What is stored in Electronics Lab?",
                "What locations do we have?",
            ],
        )

    location = _closest_location_match(location_query)
    if not location:
        return (
            f'No location matching "{location_query}" was found.',
            [
                "What do we have in Mechanical Workshop?",
                "What locations do we have?",
            ],
        )

    items = get_by_location(location)
    if not items:
        return (
            f'No items found stored in "{location}".',
            [
                "What do we have in Mechanical Workshop?",
                "What locations do we have?",
            ],
        )

    ans = f'Items stored in "{location}":\n' + _format_items(items)
    first_item = items[0]["name"]
    return (
        ans,
        [
            f"How many {first_item} do we have?",
            f"Where is {first_item} stored?",
            "What locations do we have?",
        ],
    )


def _handle_locations(text: str = "") -> Tuple[str, List[str]]:
    locations = get_all_locations()
    if not locations:
        return ("There are currently no locations recorded.", ["Show all inventory."])

    locations = sorted(set(locations))
    return (
        "Available storage locations:\n" + "\n".join(f"- {loc}" for loc in locations),
        [
            "What do we have in Mechanical Workshop?",
            "What do we have in Composites Room?",
            "What categories do we have?",
        ],
    )


INTENT_HANDLERS: Dict[str, Callable[[str], Tuple[str, List[str]]]] = {
    INTENT_QUANTITY: _handle_quantity,
    INTENT_LOCATION: _handle_location,
    INTENT_CATEGORY_LIST: _handle_category_list,
    INTENT_EXISTS: _handle_exists,
    INTENT_ALL_INVENTORY: _handle_all_inventory,
    INTENT_LOW_STOCK: _handle_low_stock,
    INTENT_CATEGORY_COUNT: _handle_category_count,
    INTENT_CATEGORIES: _handle_categories,
    INTENT_LOCATION_LIST: _handle_location_list,
    INTENT_LOCATIONS: _handle_locations,
}


# ============================================================
# MAIN ASSISTANT ENTRYPOINTS
# ============================================================

def answer_question_with_suggestions(raw_text: str) -> Tuple[str, List[str]]:
    """
    Accept natural language query and return tuple of (base_answer, list_of_suggested_follow_up_questions).
    """
    if not raw_text or not raw_text.strip():
        return (
            'Please type a question — for example: "How many brake pads do we have?"',
            [
                "How many brake pads do we have?",
                "Where is the ECU?",
                "What categories do we have?",
            ],
        )

    text = _normalize(raw_text)
    intent = detect_intent(text)

    handler = INTENT_HANDLERS.get(intent)
    if handler:
        return handler(text)

    return (
        FALLBACK_MSG,
        [
            "How many brake pads do we have?",
            "Where is the ECU?",
            "Show all inventory.",
        ],
    )


def answer_question(raw_text: str) -> str:
    """
    Main entry point for text-only/CLI usage. Returns answer string with formatted follow-ups.
    """
    base_answer, suggestions = answer_question_with_suggestions(raw_text)
    if suggestions:
        bullet_points = "\n".join(f"- {q}" for q in suggestions)
        return f"{base_answer}\n\nSuggested follow-up questions:\n{bullet_points}"
    return base_answer


# ============================================================
# TERMINAL TEST MODE
# ============================================================

if __name__ == "__main__":
    print("CURT Inventory Assistant - Phase 1")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        print("\nAssistant:")
        print(answer_question(question))
        print()
