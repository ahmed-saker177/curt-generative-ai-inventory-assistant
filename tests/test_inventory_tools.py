"""Tests for the controlled inventory tool layer used by Phase 2."""

import unittest

from backend.app.data.db import init_db
from backend.app.tools.inventory_tools import (
    TOOL_HANDLERS,
    check_stock,
    execute_tool,
    list_by_category,
)


class InventoryToolTests(unittest.TestCase):
    """Ensure tool calls remain database-backed and safely allow-listed."""

    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def test_required_tools_are_registered(self) -> None:
        self.assertTrue(
            {"check_stock", "list_by_category", "flag_shortage"}.issubset(
                TOOL_HANDLERS
            )
        )

    def test_stock_lookup_handles_typo(self) -> None:
        result = check_stock("brek pads")
        self.assertTrue(result["found"])
        self.assertEqual(result["part"]["name"], "Brake Pads")
        self.assertEqual(result["part"]["quantity"], 12)

    def test_category_lookup_returns_matching_parts_only(self) -> None:
        result = list_by_category("Brakes")
        self.assertTrue(result["found"])
        self.assertEqual(result["count"], 2)
        self.assertEqual({item["category"] for item in result["items"]}, {"Brakes"})

    def test_low_stock_and_summary_tools(self) -> None:
        low_stock = execute_tool("list_low_stock", {})
        summary = execute_tool("inventory_summary", {})
        self.assertGreater(low_stock["count"], 0)
        self.assertEqual(summary["part_types"], 11)

    def test_unknown_tool_is_rejected(self) -> None:
        self.assertIn("error", execute_tool("delete_inventory", {}))
