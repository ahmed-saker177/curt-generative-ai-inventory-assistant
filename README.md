# CURT Inventory Assistant

Phase 1 is a deterministic, rule-based inventory assistant for CURT. It uses a single SQLite database and does not call an external AI model.

## Completed Phase 1 features

- SQLite `parts` table with 11 seeded motorsport inventory parts.
- Data-access layer in `db.py` for inventory queries and quantity updates.
- Rule-based free-text questions for quantities, locations, and categories.
- Fuzzy matching for misspelled part names, plus clear responses for unknown and ambiguous requests.
- Streamlit chat interface with a live inventory sidebar, metrics, filtering, example prompts, and follow-up questions.

## Architecture

```text
Streamlit UI -> phase1_assistant.py -> db.py -> SQLite (curt_inventory.db)
```

`phase1_assistant.py` identifies an intent with keyword and rule scoring, extracts an item/category/location, then retrieves the answer through `db.py`. The assistant never writes raw SQL itself.

## Local setup

1. Install the project dependencies with `uv sync`.
2. Start the frontend with `uv run streamlit run streamlit_app.py`.
3. Open the local URL shown by Streamlit.

The database is created and seeded automatically when the application starts. To run the Phase 1 checks:

```bash
python -m unittest discover -s tests
```

## Supported questions

- `How many brake pads do we have?`
- `Where is the ECU?`
- `List all items in Brakes.`

Additional supported queries include low-stock checks, full inventory lists, category/location lists, and queries for a specific storage location.

## Edge-case decisions

- **Unknown item:** explain that no matching inventory item was found and suggest next questions.
- **Misspelled or partial item:** use exact, partial, and fuzzy matching against known part names.
- **Ambiguous question:** ask the user to identify the item rather than assuming one.

## Next phase

Phase 2 will add a FastAPI backend, LLM function calling, `/chat` and `/inventory` endpoints, and per-session conversation memory while continuing to use the same SQLite database.
