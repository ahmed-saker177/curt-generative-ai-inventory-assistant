"""Regression tests for required Phase 1 CURT assistant behavior."""

import unittest

from backend.app.data.db import get_all_parts, init_db
from phase1.assistant import answer_question_with_suggestions


class Phase1AssistantTests(unittest.TestCase):
    """Verify database-backed rules required for the Phase 1 assistant."""

    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def test_seeded_inventory_has_required_volume(self) -> None:
        self.assertGreaterEqual(len(get_all_parts()), 10)

    def test_quantity_question(self) -> None:
        answer, _ = answer_question_with_suggestions("How many brake pads do we have?")
        self.assertIn("12 Brake Pads", answer)

    def test_location_question(self) -> None:
        answer, _ = answer_question_with_suggestions("Where is the ECU?")
        self.assertIn("Electronics Lab, Shelf B", answer)

    def test_category_question(self) -> None:
        answer, _ = answer_question_with_suggestions("List all items in Brakes.")
        self.assertIn('Items in category "Brakes"', answer)
        self.assertIn("Brake Pads", answer)
        self.assertNotIn("ECU", answer)

    def test_edge_cases(self) -> None:
        unknown_answer, _ = answer_question_with_suggestions("How many turbochargers do we have?")
        typo_answer, _ = answer_question_with_suggestions("How many brek pads?")
        ambiguous_answer, _ = answer_question_with_suggestions("How many do we have?")

        self.assertIn("couldn't find", unknown_answer)
        self.assertIn("12 Brake Pads", typo_answer)
        self.assertIn("Which item do you mean?", ambiguous_answer)


if __name__ == "__main__":
    unittest.main()
