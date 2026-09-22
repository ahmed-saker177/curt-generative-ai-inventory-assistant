# CURT Inventory Assistant — Deployment & Database Guide

This guide explains how to deploy the CURT Inventory Assistant, how the SQLite database is managed, and how to provide, persist, or pre-load a database across different deployment environments.

---

## 1. Database Overview

The CURT Inventory Assistant uses a high-performance, embedded SQLite database:
- **Location:** Configured by the `CURT_DB_PATH` environment variable.
  - **Local Default:** `./curt_inventory.db`
  - **Docker Default:** `/data/curt_inventory.db` (inside a shared volume)
- **Automatic Self-Seeding:** If the database does not exist or has missing items, `init_db()` automatically runs on service startup and seeds the complete dataset (**52 motorsport components** across 10 racing subsystems).
- **Zero External DB Dependencies:** No PostgreSQL or MySQL servers required.

---

## 2. Deploying with Docker Compose (Recommended)

Docker Compose runs both the FastAPI backend and Streamlit frontend in isolated containers sharing a persistent database volume.

### Step 1: Configure Environment
Ensure your `.env` file exists with your LLM credentials:
```bash
cp .env.example .env
# Edit .env and supply your GROQ_API_KEY
```

### Step 2: Start Services
```bash
docker compose up -d --build
```
- **Streamlit Frontend:** Accessible at `http://<your-server-ip>:8502` (or mapped port `8501`)
- **FastAPI Backend:** Accessible at `http://<your-server-ip>:8000` (`/docs` for Swagger UI)
- The database is automatically created and seeded in the `curt_inventory_data` volume.

---

## 3. How to Provide Your Own Custom Database to Deployment

If you have pre-populated a `curt_inventory.db` file (or want to migrate existing workshop data into your deployment), you have three easy methods:

### Method A: Docker Volume Copy (Quickest on Running Server)
If your container is already running:
```bash
# Copy your local database file directly into the shared Docker volume
docker compose cp curt_inventory.db api:/data/curt_inventory.db

# Restart services to load the updated database
docker compose restart
```

### Method B: Host Bind Mount (Best for Direct Server File Access)
To manage the database file directly on the host machine disk:
1. In `docker-compose.yml`, change the volume mounts from the named volume `curt_inventory_data:/data` to a host directory:
```yaml
services:
  api:
    ...
    volumes:
      - ./backend:/app/backend
      - ./data:/data         # <-- Bind mount to host directory
  
  frontend:
    ...
    volumes:
      - ./frontend:/app/frontend
      - ./backend:/app/backend
      - ./phase1:/app/phase1
      - ./data:/data         # <-- Shared with frontend
```
2. Place your `curt_inventory.db` inside `./data/curt_inventory.db` on your host machine.
3. Run `docker compose up -d`.

### Method C: Pre-bake Database into Docker Images (Self-Contained Image)
If deploying to a platform without volume storage (e.g. standard container registries):
Add the following line into `backend/Dockerfile` and `frontend/Dockerfile` before the CMD:
```dockerfile
COPY curt_inventory.db /data/curt_inventory.db
```

---

## 4. Deploying to Cloud Platforms

### A. Render / Railway / Fly.io
1. **Repository:** Connect your GitHub repository.
2. **Environment Variables:**
   - `GROQ_API_KEY`: Your Groq API key
   - `LLM_PROVIDER`: `groq`
   - `CURT_DB_PATH`: `/data/curt_inventory.db`
3. **Persistent Disk (Important):** Attach a persistent disk mounted at `/data` (1 GB is more than enough). This ensures any quantity updates or additions are preserved across redeploys.
4. **Build & Start Commands:**
   - **Backend Service:**
     - Build: `pip install uv && uv sync`
     - Start: `uv run uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Frontend Service:**
     - Build: `pip install uv && uv sync`
     - Start: `uv run streamlit run frontend/streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
     - Environment variable: `BACKEND_URL=https://your-backend-service.onrender.com`

### B. Streamlit Community Cloud (Quick Frontend Demo)
1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and select your repository.
3. Main file path: `frontend/streamlit_app.py`
4. In Advanced Settings, add secrets:
   ```toml
   BACKEND_URL = "https://your-fastapi-backend-url"
   GROQ_API_KEY = "gsk_..."
   ```
5. Deploy! Streamlit will automatically initialize the local 52-part database on boot.

---

## 5. Database Maintenance & Admin Commands

### Re-seed Database to Default 52 Motorsport Parts
If data was altered and you want to cleanly restore the 52 canonical parts:
```bash
# Via Python one-liner
uv run python -c "from backend.app.data.db import reseed_db; count = reseed_db(); print(f'Database reseeded with {count} parts.')"
```

### Inspect Database Inventory
```bash
uv run python -c "from backend.app.data.db import get_all_parts; [print(f\"{p['id']}. {p['name']} ({p['category']}): {p['quantity']} units @ {p['location']}\") for p in get_all_parts()]"
```

### Backup Database File
```bash
# SQLite online safe backup
sqlite3 curt_inventory.db ".backup curt_inventory_backup.db"
```
Or use the **"📥 CSV Export"** button in the Streamlit frontend sidebar to instantly download a CSV snapshot of the entire inventory table.
