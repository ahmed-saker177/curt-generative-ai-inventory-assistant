"""Structural tests for the Phase 2 FastAPI layer and memory store."""

import unittest
from unittest.mock import patch

from backend.app.api.routes.health import health
from backend.app.api.routes.inventory import inventory
from backend.app.data.db import init_db
from backend.app.main import app
from backend.app.services.conversation_memory import ConversationStore
from backend.app.services.llm_service import ChatService, LLMConfigurationError


class Phase2ApiTests(unittest.TestCase):
    """Verify API routes, shared database reads, and bounded session memory."""

    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def test_required_routes_exist(self) -> None:
        route_paths = set(app.openapi()["paths"])
        self.assertTrue({"/chat", "/inventory"}.issubset(route_paths))

    def test_inventory_endpoint_uses_seeded_database(self) -> None:
        self.assertEqual(health().status, "ok")
        self.assertEqual(len(inventory()), 11)

    def test_conversation_store_keeps_recent_turns(self) -> None:
        store = ConversationStore(max_messages_per_session=4)
        store.append_turn("session-a", "First question", "First answer")
        store.append_turn("session-a", "Second question", "Second answer")
        store.append_turn("session-a", "Third question", "Third answer")

        history = store.get_history("session-a")
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0].content, "Second question")
        self.assertEqual(history[-1].content, "Third answer")

    def test_invalid_provider_is_rejected_before_any_network_call(self) -> None:
        with patch.dict("os.environ", {"LLM_PROVIDER": "invalid"}, clear=False):
            with self.assertRaises(LLMConfigurationError):
                ChatService().respond("session-a", "How many brake pads do we have?")
