# 🏎️ CURT Inventory Assistant

An intelligent, dual-engine inventory management system engineered for the **Cairo University Racing Team (CURT) Formula Student / FSAE** racing car project.

The application allows race engineers, mechanics, and logistics leads to query parts, check stock, verify storage locations, inspect low-stock thresholds, and flag component shortages through two complementary engines:
- **Phase 1: Deterministic Rule-Based Engine** — Fast, offline, heuristic intent parser using keyword scoring, entity extraction, and fuzzy matching with zero external API dependencies.
- **Phase 2: Autonomous LLM Agent** — Powered by Groq or Google Gemini with multi-turn conversation memory, schema-validated tool calling, and automated database lookups.

## Documentation

- [Technical Questions & Answers](docs/technical_questions_answers.pdf)
- [Project Architecture](#architecture)
- [API Documentation](docs/api_documentation.md) (or [Quick Reference](#api))

---

## 📋 Table of Contents
- [Documentation](#documentation)
- [Tech Stack](#-tech-stack)
- [Project Architecture](#architecture)
- [Local Environment Setup](#-local-environment-setup)
  - [Prerequisites](#prerequisites)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Install Dependencies](#step-2-install-dependencies)
  - [Step 3: Configure Environment Variables](#step-3-configure-environment-variables)
  - [Step 4: Database Seeding & Verification](#step-4-database-seeding--verification)
  - [Step 5: Run the Application Locally](#step-5-run-the-application-locally)
  - [Step 6: Run Automated Tests](#step-6-run-automated-tests)
- [API Documentation](#api)
- [Phase 2 Function-Calling Tools](#-phase-2-function-calling-tools)
- [Edge-Case Handling & Decisions](#-edge-case-handling--decisions)
- [Task 6: Reflection & Future Improvements](#-task-6-reflection--future-improvements)
- [Docker & Deployment](#-docker--deployment)

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12+) | Async REST API, OpenAPI docs, and request routing |
| **Frontend UI** | [Streamlit](https://streamlit.io/) (1.64+) | Interactive chat interface, live telemetry cards, and data table |
| **Database** | [SQLite](https://sqlite.org/) | Embedded, zero-configuration relational database |
| **Data Validation** | [Pydantic v2](https://docs.pydantic.dev/) | Strict request/response schemas and tool parameter validation |
| **LLM Orchestration** | [Groq](https://groq.com/) & [Google GenAI](https://ai.google.dev/) | Function-calling agents with multi-turn conversation store |
| **Package Management** | [uv](https://docs.astral.sh/uv/) / `pip` | High-speed dependency resolution and virtual environments |
| **Containerization** | [Docker](https://www.docker.com/) & Docker Compose | Multi-container reproducible deployment |

---

<a id="architecture"></a>
## 🏗️ Project Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Streamlit Frontend (:8501)                      │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐   │
│   │   Phase 1: Rule-Based Tab   │    │     Phase 2: LLM Agent Tab  │   │
│   └──────────────┬──────────────┘    └──────────────┬──────────────┘   │
└──────────────────┼──────────────────────────────────┼──────────────────┘
                   │                                  │ HTTP /chat
                   ▼                                  ▼
      ┌─────────────────────────┐        ┌────────────────────────────┐
      │  phase1/assistant.py    │        │   FastAPI Backend (:8000)  │
      │  • Keyword Scoring      │        │   • Session Memory Store   │
      │  • Intent Extraction    │        │   • API Routes (/chat)     │
      │  • Fuzzy difflib Match  │        └────────────┬───────────────┘
      └────────────┬────────────┘                     │
                   │                                  ▼
                   │                     ┌────────────────────────────┐
                   │                     │   services/llm_service.py  │
                   │                     │   • Groq / Gemini Client   │
                   │                     │   • Autonomous Agent Loop  │
                   │                     └────────────┬───────────────┘
                   │                                  │ Tool Calling
                   │                                  ▼
                   │                     ┌────────────────────────────┐
                   │                     │ tools/inventory_tools.py   │
                   │                     │ • check_stock, list_*, ... │
                   │                     └────────────┬───────────────┘
                   │                                  │
                   ▼                                  ▼
      ┌───────────────────────────────────────────────────────────────┐
      │                     backend/app/data/db.py                    │
      │                     (Shared Data-Access Layer)                │
      └───────────────────────────────┬───────────────────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │ SQLite (curt_inventory.db)│
                        │ • 11 FSAE Subsystem Parts │
                        └───────────────────────────┘
```

---

## 💻 Local Environment Setup

Follow these step-by-step instructions to install, configure, and run the CURT Inventory Assistant on your local machine.

### Prerequisites
- **Python 3.12+** installed on your system.
- **Git** installed.
- (Recommended) [uv](https://docs.astral.sh/uv/) package manager for ultra-fast dependency installation. Alternatively, standard Python `venv` + `pip` works out-of-the-box.

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/<your-username>/curt-generative-ai-inventory-assistant.git
cd curt-generative-ai-inventory-assistant
```

---

### Step 2: Install Dependencies

You can choose either **Option A (Fastest with `uv`)** or **Option B (Standard `pip`)**:

#### Option A: Using `uv` (Recommended)
If you don't have `uv` installed yet, install it via:
```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Sync all project dependencies into an isolated virtual environment:
```bash
uv sync
```

#### Option B: Using Standard Python `venv` & `pip`
```bash
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate the virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (cmd.exe):
.venv\Scripts\activate.bat
# On macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -e .
```

---

### Step 3: Configure Environment Variables

The project includes a `.env.example` template with all necessary configuration flags.

1. **Create your `.env` file**:
   ```bash
   # On Windows (PowerShell):
   Copy-Item .env.example .env

   # On macOS / Linux:
   cp .env.example .env
   ```

2. **Select and configure your LLM Provider** in `.env`:

   ```ini
   # Select exactly one provider for Phase 2: 'groq' or 'gemini'
   LLM_PROVIDER=groq

   # Option 1: Groq Configuration (Free, ultra-fast inference)
   # Get your free key at: https://console.groq.com/keys
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=openai/gpt-oss-120b

   # Option 2: Google Gemini Configuration (Alternative)
   # Get your key at: https://aistudio.google.com/app/apikey
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-flash-latest

   # Optional Service Settings:
   BACKEND_URL=http://localhost:8000
   CURT_DB_PATH=curt_inventory.db
   ```

> 🔒 **Security Notice:** `.env` is ignored by `.gitignore`. Never commit actual API keys to GitHub.

---

### Step 4: Database Seeding & Verification

The application uses an embedded SQLite database (`curt_inventory.db`). 

- **Automatic Seeding:** You do not need to run manual migration scripts. When either FastAPI or Streamlit boots, `init_db()` automatically runs, creates the `parts` table if missing, and seeds it with **11 canonical FSAE motorsport parts** spanning 8 racing subsystems (Brakes, Electronics, Chassis, Suspension, Cockpit, Cooling, Tires, Engine).
- **Manual Verification:** If you wish to inspect the database before starting the servers, run:
  ```bash
  # Using uv:
  uv run python -c "from backend.app.data.db import init_db, get_all_parts; init_db(); print(f'Seeded {len(get_all_parts())} parts successfully.')"

  # Or using active python venv:
  python -c "from backend.app.data.db import init_db, get_all_parts; init_db(); print(f'Seeded {len(get_all_parts())} parts successfully.')"
  ```

---

### Step 5: Run the Application Locally

To use both Phase 1 and Phase 2, open **two terminal windows**:

#### Terminal 1: Start the FastAPI Backend
```bash
# Using uv:
uv run uvicorn backend.app.main:app --reload --port 8000

# Or with activated venv:
uvicorn backend.app.main:app --reload --port 8000
```
- **Backend API:** Available at `http://localhost:8000`
- **Interactive Swagger Docs:** Available at `http://localhost:8000/docs`
- **Alternative ReDoc:** Available at `http://localhost:8000/redoc`

#### Terminal 2: Start the Streamlit Frontend
```bash
# Using uv:
uv run streamlit run frontend/streamlit_app.py

# Or with activated venv:
streamlit run frontend/streamlit_app.py
```
- **Streamlit Web UI:** Automatically opens in your browser at `http://localhost:8501`

---

### Quick Verification & Testing Workflow

| Testing Mode | Setup Required | Description |
| :--- | :--- | :--- |
| **Phase 1 (Rule-Based)** | Streamlit only | Works **100% offline** without running FastAPI or providing any LLM keys. Select "Rule-Based (P1)" in the top header and type queries like *"How many brake pads do we have?"*. |
| **Phase 2 (LLM Agent)** | FastAPI + Streamlit + `.env` | Full agentic workflow. Switch to "AI Agent (P2)" in the top header. The UI displays the live backend health status (`FastAPI READY / LIVE`), runs multi-turn conversations, shows executed tools, and updates telemetry. |

---

### Step 6: Run Automated Tests

The repository contains unit tests covering Phase 1 heuristic parsing, Phase 2 tool validation, and FastAPI route responses:

```bash
# Run tests with unittest (standard library):
python -m unittest discover -s tests

# Or run with uv:
uv run python -m unittest discover -s tests
```

---



## 🔧 Phase 2 Function-Calling Tools

The LLM is strictly decoupled from direct database writes. All actions pass through the allowlisted tools defined in `backend/app/tools/inventory_tools.py`:

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `check_stock` | `item_name: str` | Retrieves exact count, category, and storage location for a part (supports fuzzy matching). |
| `list_by_category` | `category: str` | Lists all parts belonging to a specified subsystem category. |
| `list_by_location` | `location: str` | Lists all parts stored in a specific workshop or storage room. |
| `list_low_stock` | `threshold: int = 5` | Finds parts at or below a stock threshold needing reorder. |
| `list_inventory` | None | Returns the full parts catalog. |
| `list_categories` | None | Returns distinct subsystem categories. |
| `list_locations` | None | Returns distinct storage locations. |
| `inventory_summary` | None | Returns aggregated counts: total part SKUs, total units, and low-stock count. |
| `flag_shortage` | `item_name: str` | Emits a structured critical shortage alert in backend telemetry. |

---

## 🎯 Edge-Case Handling & Decisions

### 1. Misspelled or Colloquial Part Names
- **Implementation:** Both Phase 1 and Phase 2 tools utilize a 3-tier resolution strategy:
  1. Exact case-insensitive match (`LOWER(name) = LOWER(query)`).
  2. Substring containment (`"brake"` in `"Brake Pads"`).
  3. Gestalt pattern matching via `difflib.get_close_matches` with an empirically calibrated cutoff of `0.6`.
- **Reasoning:** In a noisy garage or pit-lane setting, mechanics typing on mobile devices frequently make typos (e.g., *"brek pads"* or *"suspention spring"*). The `0.6` cutoff catches misspellings without falsely cross-matching distinct parts (e.g. preventing *"brake pads"* from resolving to *"brake discs"*).

### 2. Non-Existent or Out-of-Catalog Items
- **Implementation:** The assistant explicitly negates the request and informs the user that the part does not exist in the CURT inventory database, optionally suggesting related categories or available items.
- **Reasoning:** Hallucinating a non-existent part or reporting a false quantity risks severe pit delays and safety violations. Clear negation guarantees zero false assumptions.

### 3. Ambiguous or Incomplete Queries
- **Implementation:** If a user submits an entity-free inquiry (e.g., *"How many do we have?"* or *"Where is it?"*), Phase 1 prompts the user directly for clarification (*"Which item would you like to check?"*), and Phase 2 leverages conversational history to disambiguate or politely requests clarification.
- **Reasoning:** Prevents random guessing and enforces predictable inventory audits.

### 4. Engine Mode Isolation
- **Implementation:** The Streamlit frontend maintains separate message stores for Phase 1 and Phase 2.
- **Reasoning:** Allows evaluators to test Phase 1's deterministic parser independently from Phase 2's LLM agent without pollution from prior context.

---

## 📝 Task 6: Reflection & Future Improvements

### Edge-Case Decisions & Architectural Rationale
- **Zero Raw SQL for the LLM:** We deliberately restricted the LLM to predefined, schema-validated Python functions instead of providing raw SQL execution. This eliminates SQL injection risks and prevents hallucinated SQL table joins.
- **In-Memory Thread-Safe Session Store:** For Phase 2, `ConversationStore` keeps sliding window history per `session_id`, ensuring follow-up queries (*"Where is it stored?"* after asking about the ECU) resolve naturally without state leakage across users.

### What We Would Add With More Time
1. **Multimodal RAG with Technical Datasheets:** Integrate a vector database (e.g. ChromaDB or Qdrant) alongside SQLite to store PDF technical datasheets, CAD assembly guidelines, wiring pinouts, and tightening torques. Team members could query part locations and assembly specifications simultaneously.
2. **Persistent Distributed Sessions:** Replace the in-memory session store with Redis to enable horizontal scaling of the FastAPI backend across multiple container replicas.
3. **Automated Reorder Webhooks:** Connect `flag_shortage` to Slack / Discord / WhatsApp webhooks to immediately ping CURT's manufacturing and supply chain leads when critical stock falls below safety margins.
4. **Role-Based Access Control (RBAC):** Add user authentication with granular roles: pit crew can inspect and request parts; inventory leads can approve replenishment and alter quantities.

---

## 🐳 Docker & Deployment

### Quick Run with Docker Compose
If you have Docker and Docker Compose installed:
```bash
# 1. Create .env with your LLM key
cp .env.example .env

# 2. Build and launch containers
docker compose up --build
```
- **Streamlit:** `http://localhost:8501`
- **FastAPI:** `http://localhost:8000` (`/docs` for interactive API docs)

For detailed deployment instructions on **Railway**, **Render**, or **Streamlit Community Cloud**, see [DEPLOYMENT.md](file:///d:/ahmed/AI-Projects/CURT/DEPLOYMENT.md).

---

## 👥 Credits
**Cairo University Racing Team (CURT)** — Formula Student Season 26-27 Technical Task.
