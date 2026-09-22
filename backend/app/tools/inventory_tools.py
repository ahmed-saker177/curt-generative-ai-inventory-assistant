"""Controlled FastAPI backend tools exposed to the Phase 2 LLM.

The LLM can request these functions but never receives database access.
"""

import difflib
import logging
import re
from collections.abc import Callable
from typing import Any

from ..data.db import (
    get_all_categories,
    get_all_locations,
    get_all_parts,
    get_by_category,
    get_by_location,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_LOW_STOCK_THRESHOLD = 5


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _resolve_value(query: str, values: list[str]) -> str | None:
    """Resolve an exact, partial, or close match from known inventory values."""
    normalized_query = _normalize(query)
    if not normalized_query:
        return None

    normalized_values = {_normalize(value): value for value in values}
    if normalized_query in normalized_values:
        return normalized_values[normalized_query]

    partial_matches = [
        value
        for normalized_value, value in normalized_values.items()
        if normalized_query in normalized_value or normalized_value in normalized_query
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]

    close_matches = difflib.get_close_matches(
        normalized_query, normalized_values.keys(), n=1, cutoff=0.6
    )
    if close_matches:
        return normalized_values[close_matches[0]]
    return None


def _find_part(item_name: str) -> dict[str, Any] | None:
    """Find one inventory part using safe in-memory matching."""
    parts = get_all_parts()
    match = _resolve_value(item_name, [part["name"] for part in parts])
    if not match:
        return None
    return next(part for part in parts if part["name"] == match)


def check_stock(item_name: str) -> dict[str, Any]:
    """Return the quantity and location of one inventory part."""
    part = _find_part(item_name)
    if not part:
        return {
            "found": False,
            "message": f'No inventory part matches "{item_name}".',
        }

    return {
        "found": True,
        "part": part,
        "is_low_stock": part["quantity"] <= DEFAULT_LOW_STOCK_THRESHOLD,
        "low_stock_threshold": DEFAULT_LOW_STOCK_THRESHOLD,
    }


def list_by_category(category: str) -> dict[str, Any]:
    """Return all parts in a requested category."""
    matched_category = _resolve_value(category, get_all_categories())
    if not matched_category:
        return {
            "found": False,
            "message": f'No inventory category matches "{category}".',
        }

    items = get_by_category(matched_category)
    return {
        "found": True,
        "category": matched_category,
        "items": items,
        "count": len(items),
        "total_units": sum(item["quantity"] for item in items),
    }


def list_by_location(location: str) -> dict[str, Any]:
    """Return all parts stored at a requested location."""
    matched_location = _resolve_value(location, get_all_locations())
    if not matched_location:
        return {
            "found": False,
            "message": f'No inventory location matches "{location}".',
        }

    items = get_by_location(matched_location)
    return {
        "found": True,
        "location": matched_location,
        "items": items,
        "count": len(items),
        "total_units": sum(item["quantity"] for item in items),
    }


def list_inventory() -> dict[str, Any]:
    """Return every currently stored inventory part."""
    items = get_all_parts()
    return {
        "items": items,
        "count": len(items),
        "total_units": sum(item["quantity"] for item in items),
    }


def list_low_stock(threshold: int = DEFAULT_LOW_STOCK_THRESHOLD) -> dict[str, Any]:
    """Return parts at or below a caller-supplied stock threshold."""
    if threshold < 0:
        return {"error": "threshold must be zero or greater."}

    items = [part for part in get_all_parts() if part["quantity"] <= threshold]
    return {"threshold": threshold, "items": items, "count": len(items)}


def list_categories() -> dict[str, Any]:
    """Return all available part categories."""
    categories = get_all_categories()
    return {"categories": categories, "count": len(categories)}


def list_locations() -> dict[str, Any]:
    """Return all available storage locations."""
    locations = get_all_locations()
    return {"locations": locations, "count": len(locations)}


def inventory_summary() -> dict[str, Any]:
    """Return aggregate inventory totals for dashboard-style questions."""
    items = get_all_parts()
    return {
        "part_types": len(items),
        "total_units": sum(item["quantity"] for item in items),
        "category_count": len(get_all_categories()),
        "location_count": len(get_all_locations()),
        "low_stock_count": sum(
            item["quantity"] <= DEFAULT_LOW_STOCK_THRESHOLD for item in items
        ),
        "low_stock_threshold": DEFAULT_LOW_STOCK_THRESHOLD,
    }


def flag_shortage(item_name: str) -> dict[str, Any]:
    """Log a shortage flag when a matching part is at or below the threshold."""
    stock_result = check_stock(item_name)
    if not stock_result["found"]:
        return stock_result

    part = stock_result["part"]
    if not stock_result["is_low_stock"]:
        return {
            "flagged": False,
            "message": (
                f'{part["name"]} has {part["quantity"]} units and is not below '
                f'the threshold of {DEFAULT_LOW_STOCK_THRESHOLD}.'
            ),
        }

    LOGGER.warning(
        "Inventory shortage flagged: %s has %s units at %s",
        part["name"],
        part["quantity"],
        part["location"],
    )
    return {
        "flagged": True,
        "part": part,
        "message": f'Shortage flag logged for {part["name"]}.',
    }


INVENTORY_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "check_stock",
        "description": "Get the current quantity, category, and storage location for one part.",
        "parameters": {
            "type": "object",
            "properties": {"item_name": {"type": "string"}},
            "required": ["item_name"],
        },
    },
    {
        "type": "function",
        "name": "list_by_category",
        "description": "List all parts and totals in one inventory category.",
        "parameters": {
            "type": "object",
            "properties": {"category": {"type": "string"}},
            "required": ["category"],
        },
    },
    {
        "type": "function",
        "name": "list_by_location",
        "description": "List all parts and totals stored at one location.",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    },
    {
        "type": "function",
        "name": "list_inventory",
        "description": "List the complete current inventory.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "list_low_stock",
        "description": "List parts at or below a stock threshold. Use the default when none is requested.",
        "parameters": {
            "type": "object",
            "properties": {"threshold": {"type": "integer", "minimum": 0}},
        },
    },
    {
        "type": "function",
        "name": "list_categories",
        "description": "List every inventory category.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "list_locations",
        "description": "List every storage location.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "inventory_summary",
        "description": "Get totals for part types, units, categories, locations, and low-stock items.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "flag_shortage",
        "description": "Log a low-stock shortage flag for a specific part. Use when the user asks to flag or alert a shortage.",
        "parameters": {
            "type": "object",
            "properties": {"item_name": {"type": "string"}},
            "required": ["item_name"],
        },
    },
]

GROQ_TOOL_DEFINITIONS = [
    {"type": "function", "function": definition}
    for definition in INVENTORY_TOOL_DEFINITIONS
]

TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "check_stock": check_stock,
    "list_by_category": list_by_category,
    "list_by_location": list_by_location,
    "list_inventory": list_inventory,
    "list_low_stock": list_low_stock,
    "list_categories": list_categories,
    "list_locations": list_locations,
    "inventory_summary": inventory_summary,
    "flag_shortage": flag_shortage,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run one allow-listed tool and return a JSON-serializable result."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f'Unknown tool "{name}".'}
    if not isinstance(arguments, dict):
        return {"error": "Tool arguments must be a JSON object."}

    try:
        return handler(**arguments)
    except TypeError:
        return {"error": f'Invalid arguments for tool "{name}".'}
