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
Phase 1
Streamlit UI -> phase1_assistant.py -> db.py -> SQLite (curt_inventory.db)

Phase 2
Streamlit UI -> FastAPI -> llm_service.py -> controlled inventory_tools.py -> db.py -> SQLite
                                      |                         |
                                      +--> Groq or Gemini <-----+
```

`phase1_assistant.py` identifies an intent with keyword and rule scoring, extracts an item/category/location, then retrieves the answer through `db.py`. The assistant never writes raw SQL itself.

For Phase 2, FastAPI owns the API, session memory, and LLM orchestration. The LLM chooses from an allow-list of tools, but the backend validates and executes every call locally. It has no direct SQLite access.

## Local setup

1. Install the project dependencies with `uv sync`.
2. Copy `.env.example` to `.env` and configure one LLM provider.
3. Start the Phase 1 frontend with `uv run streamlit run streamlit_app.py`.
4. Start the Phase 2 backend with `uv run uvicorn main:app --reload`.

FastAPI docs are available at `http://127.0.0.1:8000/docs` while the backend is running.

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

## Phase 2 API

### `GET /inventory`

Returns the current shared SQLite inventory as JSON.

### `POST /chat`

Accepts a user message and optional session ID. If no session ID is supplied, the backend creates one. Reuse the returned ID for follow-up questions.

```json
{
  "message": "How many brake pads do we have?",
  "session_id": "optional-session-id"
}
```

The response includes the answer, provider, session ID, and the names of tools used by the LLM.

## Phase 2 tools

- `check_stock(item_name)` — quantity, category, and location for a part.
- `list_by_category(category)` and `list_by_location(location)` — matching parts and totals.
- `list_inventory()`, `list_categories()`, `list_locations()`, and `inventory_summary()` — broader inventory questions.
- `list_low_stock(threshold)` — low-stock questions with an optional threshold.
- `flag_shortage(item_name)` — writes a low-stock flag to the backend log.

The Groq and Gemini adapters both use an agent loop: send tool definitions, execute requested backend tools, return JSON results to the model, and repeat until it produces the final answer.

## Phase 2 provider configuration

1. Copy `.env.example` to `.env`.
2. Set `LLM_PROVIDER` to either `groq` or `gemini`.
3. Add only the matching API key and optionally change its model name.

On PowerShell:

```powershell
Copy-Item .env.example .env
```

The FastAPI backend loads this file on startup. `.env` is ignored by Git, while `.env.example` is safe to commit. The API key remains server-side: Streamlit will call FastAPI, and only FastAPI calls Groq or Gemini.
