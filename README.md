# CURT Inventory Assistant

Phase 1 is a deterministic, rule-based inventory assistant for CURT. It uses a single SQLite database and does not call an external AI model.

## Completed Phase 1 features

- SQLite `parts` table with **52 seeded motorsport inventory parts** across 10 Formula Student engineering subsystems.
- Data-access layer in `db.py` for inventory queries and quantity updates with auto-sync seeding.
- Rule-based free-text questions for quantities, locations, and categories.
- Fuzzy matching for misspelled part names, plus clear responses for unknown and ambiguous requests.
- Streamlit chat interface with a live inventory sidebar, metrics, filtering, example prompts, and follow-up questions.
- Comprehensive deployment guide in [DEPLOYMENT.md](file:///d:/ahmed/AI-Projects/CURT/DEPLOYMENT.md).

## Architecture

```text
Phase 1
Streamlit UI -> phase1/assistant.py -> backend/app/data/db.py -> SQLite

Phase 2
Streamlit UI -> FastAPI routes -> services/llm_service.py -> tools/inventory_tools.py
                  |                     |                            |
                  |                     +--> Groq or Gemini           |
                  +--> schemas + data/db.py -----------------------> SQLite
```

`phase1/assistant.py` identifies an intent with keyword and rule scoring, extracts an item/category/location, then retrieves the answer through `backend/app/data/db.py`. The assistant never writes raw SQL itself.

For Phase 2, FastAPI owns the API, session memory, and LLM orchestration. The LLM chooses from an allow-list of tools, but the backend validates and executes every call locally. It has no direct SQLite access.

## Local setup

1. Install the project dependencies with `uv sync`.
2. Copy `.env.example` to `.env` and configure one LLM provider.
3. Start the Phase 1 frontend with `uv run streamlit run frontend/streamlit_app.py`.
4. Start the Phase 2 backend with `uv run uvicorn backend.app.main:app --reload`.

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

## Task 6: Reflection & Edge-Case Decisions

### 1. Edge-Case Decisions & Reasoning

* **Misspelled or Partial Part Names:**
  * *Implementation:* We built a 3-tier lookup hierarchy in both Phase 1 and Phase 2 tools: (1) exact case-insensitive match, (2) substring containment, and (3) Gestalt pattern matching via Python `difflib.get_close_matches` with a tuned `0.6` cutoff.
  * *Reasoning:* Workshop team members typing quickly on mobile devices or in noisy garages frequently use colloquial abbreviations or make typos (e.g., *"brek pads"* -> *Brake Pads*). The `0.6` threshold was selected empirically to forgive spelling errors while strictly preventing false-positive matches between distinct motorsport parts (e.g., preventing *"brake discs"* from mistakenly resolving to *"brake pads"*).

* **Non-Existent Items:**
  * *Implementation:* When an item is not present in the database, the assistant explicitly states that no record exists in the CURT inventory and suggests related categories or prompts the user to check available parts.
  * *Reasoning:* For racing teams, a hallucinated quantity or silent failure can cause catastrophic pit-lane delays. Clear negation prevents team members from assuming parts are in stock when they are not.

* **Ambiguous or Incomplete Queries:**
  * *Implementation:* If a query lacks an entity (e.g., *"How many do we have?"*), Phase 1 prompts the user directly (*"Which item do you mean?"*) and Phase 2's system prompt instructs the LLM to ask a concise clarifying follow-up rather than guessing.
  * *Reasoning:* Guessing an arbitrary part creates user confusion and potential safety risks in motorsport inventory management.

* **Engine Mode Separation (Option A):**
  * *Implementation:* The Streamlit frontend maintains dedicated, isolated conversation histories for Phase 1 and Phase 2 within the same running session.
  * *Reasoning:* Phase 1 is a deterministic rule-based heuristic parser without conversational memory, whereas Phase 2 is an LLM agent with multi-turn session memory (`session_id`). Isolating their message streams gives evaluators an unpolluted sandbox to independently benchmark Phase 1's keyword rules against Phase 2's agentic multi-turn follow-ups.

### 2. What We Would Improve With More Time

* **Vector Search & RAG for Component Manuals:** Integrate a vector database (e.g., ChromaDB or pgvector) alongside SQLite to support multimodal RAG — enabling team members to query technical datasheets, CAD assembly guides, tightening torque specs, and wiring pinouts alongside part quantities.
* **Persistent Distributed Sessions:** Migrate from the in-memory `ConversationStore` to a Redis-backed or PostgreSQL-backed session cache, enabling horizontal scaling of FastAPI across multiple instances without losing conversation history.
* **Real-Time Notification Webhooks:** Expand `flag_shortage` from backend log emission to active push notifications via Slack, Discord, or WhatsApp webhooks to immediately alert CURT's supply-chain and manufacturing leads.
* **Role-Based Access Control (RBAC) & Audit Trails:** Implement team member authentication with role-based permissions (e.g., pit crew can check stock and request parts; workshop managers can modify quantities or register new components), complete with an immutable transaction log for telemetry tracking.

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

## Project structure

```text
backend/app/
  api/routes/       FastAPI route modules
  core/             Environment-backed settings
  data/             Shared SQLite data-access layer
  schemas/          Pydantic request and response models
  services/         Conversation memory and LLM orchestration
  tools/            Controlled function-calling tools
frontend/           Streamlit user interface
phase1/             Phase 1 rule-based assistant logic
tests/              Phase 1, API, memory, and tool tests
```

## Docker Compose

After creating `.env` (required for LLM chat), start the full application with:

```bash
docker compose up --build
```

This starts FastAPI at `http://localhost:8000` and Streamlit at `http://localhost:8501`. Both containers mount the same `curt_inventory_data` Docker volume, so Phase 1 and Phase 2 use exactly the same SQLite database.
