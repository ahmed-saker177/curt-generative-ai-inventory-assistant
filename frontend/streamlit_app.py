"""Streamlit frontend for the CURT Inventory Assistant.

Cairo University Racing Team (CURT) Formula Student / FSAE.
Modern, responsive interface supporting:
- Phase 1: Deterministic rule-based assistant
- Phase 2: LLM-powered backend assistant with controlled function calling
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import streamlit as st

from backend.app.data.db import get_all_parts, init_db
from phase1.assistant import (
    DEFAULT_LOW_STOCK_THRESHOLD,
    answer_question_with_suggestions,
)

# Configuration & Constants
PAGE_TITLE = "CURT Inventory Assistant"
PAGE_ICON = "🏎️"
PHASE_1_MODE = "Phase 1: Rule-Based (Heuristic)"
PHASE_2_MODE = "Phase 2: LLM (Agentic / Tools)"

CATEGORIES_ALL = "All Categories"
STOCK_ALL = "All Stock Levels"
STOCK_LOW = "Low Stock Only (≤ 5)"
STOCK_HEALTHY = "In Stock (> 5)"

# Prompt starters without icons — clean typography-first card layout
QUICK_PROMPTS_PHASE1 = [
    # (title, query)
    ("Brake Pads Quantity", "How many brake pads do we have?"),
    ("ECU Storage Location", "Where is the ECU?"),
    ("Low Stock Alert", "Which items are low in stock?"),
    ("Browse Brakes Category", "List all items in Brakes."),
    ("Full Inventory Overview", "Show all items in inventory."),
    ("Available Categories", "What categories do we have?"),
]

QUICK_PROMPTS_PHASE2 = [
    # (title, query)
    ("Stock & Location Lookup", "How many brake pads do we have left, and where are they stored?"),
    ("Shortage Flagging", "Check the ECU count and flag a shortage if it's running low."),
    ("Detailed Category Breakdown", "List all items in the Brakes category with total count and units."),
    ("Workshop Storage Search", "What parts are stored in the Mechanical Workshop?"),
    ("Telemetry Overview", "Give me a high-level inventory telemetry summary."),
    ("Fuzzy Existence Check", "Do we have radiator hoses or cooling components in stock?"),
]

# Page configuration
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure SQLite DB exists and is seeded
init_db()


def inject_custom_styles() -> None:
    """Inject modern racing-themed CSS styles with dark/light harmony."""
    st.markdown(
        """
        <style>
        /* Modern Racing typography & theme variables */
        :root {
            --curt-red: #E10600;
            --curt-red-dark: #B30000;
            --curt-red-subtle: rgba(225, 6, 0, 0.05);
            --border-radius: 12px;
        }

        /* Top Header styling */
        .curt-header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 1.4rem;
            background: linear-gradient(135deg, rgba(225, 6, 0, 0.07) 0%, rgba(125, 125, 125, 0.03) 100%);
            border: 1px solid rgba(225, 6, 0, 0.18);
            border-radius: var(--border-radius);
            margin-bottom: 1.15rem;
        }

        .curt-badge-red {
            display: inline-block;
            background: #E10600;
            color: #FFFFFF !important;
            font-weight: 700;
            font-size: 0.74rem;
            padding: 0.22rem 0.65rem;
            border-radius: 6px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .curt-badge-gray {
            display: inline-block;
            background: rgba(125, 125, 135, 0.16);
            color: inherit;
            font-weight: 600;
            font-size: 0.74rem;
            padding: 0.22rem 0.6rem;
            border-radius: 6px;
            letter-spacing: 0.03em;
        }

        .curt-badge-tool {
            display: inline-block;
            background: rgba(40, 167, 69, 0.12);
            color: #28a745;
            font-weight: 600;
            font-size: 0.75rem;
            padding: 0.15rem 0.55rem;
            border-radius: 6px;
            border: 1px solid rgba(40, 167, 69, 0.3);
            margin-right: 0.35rem;
            margin-top: 0.25rem;
        }

        /* Sidebar enhancement */
        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(125, 125, 125, 0.15);
        }

        .sidebar-brand-card {
            text-align: center;
            padding: 0.6rem 0.5rem 0.8rem;
            margin-bottom: 0.8rem;
            border-bottom: 1px solid rgba(125, 125, 125, 0.14);
        }

        .sidebar-mode-indicator {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.6rem 0.8rem;
            background: rgba(125, 125, 125, 0.05);
            border: 1px solid rgba(125, 125, 125, 0.15);
            border-radius: 8px;
            margin-bottom: 1rem;
            font-size: 0.82rem;
        }

        /* Chat bubbles refinement - clean distinct borders without duplicate headers */
        div[data-testid="stChatMessage"] {
            border-radius: var(--border-radius);
            padding: 0.85rem 1.15rem;
            margin-bottom: 0.85rem;
            border: 1px solid rgba(125, 125, 125, 0.15);
            transition: all 0.2s ease;
        }

        /* User bubble distinct styling */
        div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
            border: 1px solid rgba(74, 144, 226, 0.28);
            background: rgba(74, 144, 226, 0.03);
            border-right: 3px solid rgba(74, 144, 226, 0.7);
        }

        /* Assistant bubble distinct styling */
        div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
            border: 1px solid rgba(225, 6, 0, 0.2);
            border-left: 4px solid #E10600 !important;
            background: linear-gradient(135deg, rgba(225, 6, 0, 0.04) 0%, rgba(125, 125, 125, 0.02) 100%);
        }

        .assistant-meta-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.5rem;
            padding-bottom: 0.35rem;
            border-bottom: 1px solid rgba(125, 125, 125, 0.1);
        }

        /* Tools executed collapsible disclosure */
        details.curt-tools-disclosure {
            margin-top: 0.65rem;
            border: 1px solid rgba(40, 167, 69, 0.28);
            background: rgba(40, 167, 69, 0.04);
            border-radius: 8px;
            padding: 0.35rem 0.65rem;
            transition: all 0.2s ease;
        }
        details.curt-tools-disclosure[open] {
            background: rgba(40, 167, 69, 0.08);
        }
        details.curt-tools-disclosure summary {
            cursor: pointer;
            font-size: 0.78rem;
            font-weight: 600;
            color: #28a745;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            list-style: none;
        }
        details.curt-tools-disclosure summary::-webkit-details-marker {
            display: none;
        }
        details.curt-tools-disclosure summary .disclosure-arrow {
            display: inline-block;
            transition: transform 0.2s ease;
            font-size: 0.7rem;
            color: #28a745;
            font-weight: 900;
        }
        details.curt-tools-disclosure[open] summary .disclosure-arrow {
            transform: rotate(90deg);
        }
        .curt-tools-count {
            background: rgba(40, 167, 69, 0.2);
            color: #28a745;
            padding: 0.05rem 0.45rem;
            border-radius: 10px;
            font-size: 0.7rem;
            font-weight: 700;
        }
        .curt-tools-body {
            margin-top: 0.45rem;
            padding-top: 0.4rem;
            border-top: 1px dashed rgba(40, 167, 69, 0.25);
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
        }

        /* Live status indicators & badges */
        .curt-status-live {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            font-size: 0.74rem;
            padding: 0.22rem 0.65rem;
            background: rgba(40, 167, 69, 0.12);
            border: 1px solid rgba(40, 167, 69, 0.35);
            color: #28a745;
            border-radius: 12px;
            font-weight: 700;
        }

        .curt-status-offline {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            font-size: 0.74rem;
            padding: 0.22rem 0.65rem;
            background: rgba(220, 53, 69, 0.12);
            border: 1px solid rgba(220, 53, 69, 0.35);
            color: #dc3545;
            border-radius: 12px;
            font-weight: 700;
        }

        .pulse-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .pulse-indicator.live {
            background-color: #28a745;
            box-shadow: 0 0 6px #28a745;
        }
        .pulse-indicator.offline {
            background-color: #dc3545;
        }

        /* Card-Style Prompt Starter Buttons: No icons, 2-line layout, auto-wrapping */
        .prompt-grid-container {
            margin-bottom: 1.25rem;
        }
        .prompt-grid-container .stButton > button {
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            justify-content: center !important;
            text-align: left !important;
            white-space: normal !important;
            word-break: break-word !important;
            height: auto !important;
            min-height: 4.8rem !important;
            padding: 0.75rem 1rem !important;
            border-radius: 10px !important;
            border: 1px solid rgba(125, 125, 125, 0.22) !important;
            background: rgba(125, 125, 125, 0.03) !important;
            transition: all 0.2s ease-in-out !important;
        }
        .prompt-grid-container .stButton > button:hover {
            border-color: #E10600 !important;
            background: rgba(225, 6, 0, 0.04) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 14px rgba(225, 6, 0, 0.12) !important;
        }
        .prompt-grid-container .stButton > button p {
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1.35 !important;
        }
        .prompt-grid-container .stButton > button p strong {
            font-size: 0.9rem !important;
            font-weight: 700 !important;
            color: inherit !important;
            display: block !important;
            margin-bottom: 0.2rem !important;
        }
        .prompt-grid-container .stButton > button p em {
            font-size: 0.8rem !important;
            opacity: 0.72 !important;
            font-style: normal !important;
            display: block !important;
        }

        /* Telemetry Cards */
        .curt-telemetry-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.25rem;
        }
        .telemetry-card {
            background: linear-gradient(135deg, rgba(125, 125, 125, 0.05) 0%, rgba(125, 125, 125, 0.02) 100%);
            border: 1px solid rgba(125, 125, 125, 0.18);
            border-radius: 10px;
            padding: 0.9rem 1.1rem;
            transition: all 0.2s ease;
        }
        .telemetry-card:hover {
            border-color: rgba(225, 6, 0, 0.35);
            box-shadow: 0 4px 12px rgba(225, 6, 0, 0.08);
        }
        .telemetry-card.alert {
            border-color: rgba(225, 6, 0, 0.38);
            background: linear-gradient(135deg, rgba(225, 6, 0, 0.06) 0%, rgba(125, 125, 125, 0.02) 100%);
        }
        .telemetry-card-title {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700;
            opacity: 0.75;
            margin-bottom: 0.25rem;
        }
        .telemetry-card-val {
            font-size: 1.85rem;
            font-weight: 800;
            line-height: 1.1;
            letter-spacing: -0.02em;
        }
        .telemetry-card-sub {
            font-size: 0.74rem;
            opacity: 0.65;
            margin-top: 0.3rem;
        }

        /* Follow-up chips styling */
        .followup-container {
            margin-top: 0.85rem;
            padding-top: 0.65rem;
            border-top: 1px dashed rgba(125, 125, 125, 0.2);
        }
        .followup-heading {
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            margin-bottom: 0.5rem;
            opacity: 0.85;
        }
        .followup-container .stButton > button {
            text-align: left !important;
            font-size: 0.84rem !important;
            padding: 0.45rem 0.8rem !important;
            border-radius: 8px !important;
            border: 1px solid rgba(125, 125, 125, 0.2) !important;
            transition: all 0.2s ease !important;
        }
        .followup-container .stButton > button:hover {
            border-color: #E10600 !important;
            color: #E10600 !important;
            background: rgba(225, 6, 0, 0.04) !important;
        }

        /* Styled Top Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 1.25rem;
            border-bottom: 2px solid rgba(125, 125, 125, 0.15);
            padding-bottom: 0.2rem;
            margin-bottom: 1.15rem;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.96rem;
            font-weight: 700;
            padding: 0.55rem 0.9rem;
            border-radius: 6px;
            transition: all 0.2s ease;
        }
        .stTabs [aria-selected="true"] {
            color: #E10600 !important;
            border-bottom: 3px solid #E10600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_backend_url() -> str:
    """Return backend base URL from environment or default to local FastAPI."""
    raw = os.getenv("BACKEND_URL", "http://localhost:8000").strip().rstrip("/")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}" if "onrender.com" in raw or "railway.app" in raw else f"http://{raw}"
    return raw


def init_session_state() -> None:
    """Initialize state variables for the current Streamlit session."""
    st.session_state.setdefault("phase1_messages", [])
    st.session_state.setdefault("phase2_sessions", {})
    initial_p2_sid = str(uuid4())
    st.session_state.setdefault("phase2_session_id", initial_p2_sid)
    st.session_state.setdefault("session_id", initial_p2_sid)
    st.session_state.setdefault("phase2_known_sessions", [initial_p2_sid])
    st.session_state.phase2_sessions.setdefault(initial_p2_sid, [])

    st.session_state.setdefault("pending_prompt", None)
    st.session_state.setdefault("selected_mode", PHASE_1_MODE)
    st.session_state.setdefault("filter_category", CATEGORIES_ALL)
    st.session_state.setdefault("filter_stock", STOCK_ALL)
    st.session_state.setdefault("filter_search", "")


def _messages() -> list:
    """Return the message list for the currently active engine mode."""
    if st.session_state.selected_mode == PHASE_1_MODE:
        return st.session_state.setdefault("phase1_messages", [])
    p2_sid = st.session_state.phase2_session_id
    return st.session_state.phase2_sessions.setdefault(p2_sid, [])


def start_new_chat() -> None:
    """Start a brand-new chat for the active engine mode without affecting the other."""
    st.session_state.pending_prompt = None
    if st.session_state.selected_mode == PHASE_1_MODE:
        st.session_state.phase1_messages = []
    else:
        new_id = str(uuid4())
        st.session_state.phase2_session_id = new_id
        st.session_state.session_id = new_id
        st.session_state.phase2_sessions[new_id] = []
        if new_id not in st.session_state.phase2_known_sessions:
            st.session_state.phase2_known_sessions.insert(0, new_id)


# Backward-compatibility alias
clear_chat_history = start_new_chat


def switch_session(target_id: str) -> None:
    """Switch the active Phase 2 session to target_id, preserving message histories."""
    target_id = target_id.strip()
    if not target_id or target_id == st.session_state.phase2_session_id:
        return
    st.session_state.phase2_session_id = target_id
    st.session_state.session_id = target_id
    st.session_state.pending_prompt = None
    st.session_state.phase2_sessions.setdefault(target_id, [])
    if target_id not in st.session_state.phase2_known_sessions:
        st.session_state.phase2_known_sessions.insert(0, target_id)


def generate_phase2_followups(last_response: str, user_question: str) -> list[str]:
    """Ask the LLM to suggest 3 short follow-up questions based on the last exchange."""
    prompt = (
        f"The user asked: '{user_question}'\n"
        f"The assistant replied: '{last_response[:600]}'\n\n"
        "Suggest exactly 3 short follow-up inventory questions the user might ask next. "
        "Output only the 3 questions as a JSON array of strings, nothing else. "
        "Example: [\"How many ECUs do we have?\", \"Where are the brake discs?\", \"List all Electronics items.\"]"
    )
    result = call_phase2_api(prompt, "__followup_gen__")
    if "error" in result:
        return []
    try:
        raw = result.get("response", "[]")
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        suggestions = json.loads(raw[start:end])
        return [str(q) for q in suggestions if isinstance(q, str)][:3]
    except Exception:
        return []


def call_phase2_api(message: str, session_id: str) -> dict:
    """Send user question to the Phase 2 FastAPI /chat endpoint."""
    url = f"{get_backend_url()}/chat"
    payload = json.dumps({"message": message, "session_id": session_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            error_body = json.loads(error.read().decode("utf-8"))
            detail = error_body.get("detail", str(error))
        except Exception:
            detail = error.reason
        return {"error": f"Backend API Error ({error.code}): {detail}"}
    except urllib.error.URLError as error:
        return {
            "error": (
                f"Cannot reach Phase 2 backend service at `{url}`.\n\n"
                f"Ensure FastAPI is running: `uv run uvicorn backend.app.main:app --reload`.\n"
                f"Error detail: {error.reason}"
            )
        }
    except Exception as error:
        return {"error": f"Unexpected request error: {str(error)}"}


@st.cache_data(ttl=3)
def check_backend_health() -> bool:
    """Check if the Phase 2 FastAPI service is responsive."""
    url = f"{get_backend_url()}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("status") == "ok"
    except Exception:
        return False


def filter_inventory(
    parts: list[dict[str, object]],
    search_term: str,
    category_filter: str,
    stock_filter: str,
) -> pd.DataFrame:
    """Apply search, category, and stock filters to the parts table."""
    dataframe = pd.DataFrame(parts)
    if dataframe.empty:
        return dataframe

    if category_filter != CATEGORIES_ALL:
        dataframe = dataframe[dataframe["category"] == category_filter]

    if stock_filter == STOCK_LOW:
        dataframe = dataframe[dataframe["quantity"] <= DEFAULT_LOW_STOCK_THRESHOLD]
    elif stock_filter == STOCK_HEALTHY:
        dataframe = dataframe[dataframe["quantity"] > DEFAULT_LOW_STOCK_THRESHOLD]

    if search_term.strip():
        normalized = search_term.strip().lower()
        dataframe = dataframe[
            dataframe["name"].str.lower().str.contains(normalized, regex=False)
            | dataframe["category"].str.lower().str.contains(normalized, regex=False)
            | dataframe["location"].str.lower().str.contains(normalized, regex=False)
        ]

    return dataframe


def _get_friendly_session_label(sid: str, is_active: bool) -> str:
    """Format session into an informative label rather than a raw UUID hash."""
    prefix = "▶ " if is_active else ""
    msgs = st.session_state.phase2_sessions.get(sid, [])
    user_first = None
    for m in msgs:
        if m.get("role") == "user":
            user_first = m.get("content", "").strip()
            break
    if user_first:
        snippet = (user_first[:24] + "...") if len(user_first) > 24 else user_first
        return f"{prefix}{snippet}"
    return f"{prefix}Session ({sid[:8]})"


def render_sidebar() -> None:
    """Render the sidebar with brand identity, active mode info, and session control."""
    with st.sidebar:
        # CURT Logo / Brand banner
        st.markdown(
            """
            <div class="sidebar-brand-card">
                <span class="curt-badge-red" style="font-size: 0.85rem; padding: 0.28rem 0.8rem;">
                    CURT RACING
                </span>
                <div style="font-weight: 700; font-size: 1.05rem; margin-top: 0.45rem;">
                    Formula Student Inventory
                </div>
                <div style="font-size: 0.78rem; opacity: 0.7;">Season 26-27 Technical Task</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Active Engine Badge (Informational - unified toggle is in top header)
        is_p2 = st.session_state.selected_mode == PHASE_2_MODE
        mode_badge_class = "curt-badge-red" if is_p2 else "curt-badge-gray"
        mode_label = "Phase 2: LLM Agent" if is_p2 else "Phase 1: Rule-Based"
        st.markdown(
            f"""
            <div class="sidebar-mode-indicator">
                <span style="opacity: 0.75; font-weight: 600;">Engine</span>
                <span class="{mode_badge_class}">{mode_label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Quick Actions & Session Management
        st.subheader("Session Control", divider="gray")
        if st.session_state.selected_mode == PHASE_1_MODE:
            st.caption("Phase 1 operates deterministically per question.")
            if st.button("Reset Conversation", use_container_width=True, key="btn_clear_phase1"):
                start_new_chat()
                st.rerun()
        else:
            active_sid = st.session_state.phase2_session_id
            known = st.session_state.get("phase2_known_sessions", [active_sid])

            session_labels = [_get_friendly_session_label(sid, sid == active_sid) for sid in known]
            chosen_label = st.selectbox(
                "History & Sessions",
                session_labels,
                index=0,
                key="session_history_select",
                help="Select a previous conversation to inspect its history.",
            )
            chosen_full = known[session_labels.index(chosen_label)]
            if chosen_full != active_sid:
                if st.button("Switch to Selected Session", use_container_width=True, key="btn_restore_session"):
                    switch_session(chosen_full)
                    st.rerun()

            if st.button("New Chat Session", use_container_width=True, key="btn_new_chat_sidebar"):
                start_new_chat()
                st.rerun()

        # Telemetry Snapshot
        parts = get_all_parts()
        if parts:
            total_parts = len(parts)
            total_units = sum(int(p["quantity"]) for p in parts)
            low_stock_parts = sum(1 for p in parts if int(p["quantity"]) <= DEFAULT_LOW_STOCK_THRESHOLD)

            st.subheader("Telemetry Snapshot", divider="gray")
            m1, m2 = st.columns(2)
            m1.metric("Part Types", total_parts)
            m2.metric("Total Units", total_units)

            low_stock_delta = f"-{low_stock_parts}" if low_stock_parts > 0 else "Optimal"
            st.metric(
                "Low Stock Items (≤5)",
                low_stock_parts,
                delta=low_stock_delta,
                delta_color="inverse",
            )

        st.caption("Cairo University Racing Team · Gen-AI Workshop")


def submit_prompt(prompt: str) -> None:
    """Route user question to the currently active assistant mode."""
    current_mode = st.session_state.selected_mode
    active_msgs = _messages()
    active_msgs.append({
        "role": "user",
        "content": prompt,
        "mode": current_mode,
    })

    if current_mode == PHASE_1_MODE:
        reply_text, follow_ups = answer_question_with_suggestions(prompt)
        active_msgs.append(
            {
                "role": "assistant",
                "content": reply_text,
                "follow_ups": follow_ups,
                "mode": PHASE_1_MODE,
            }
        )
    else:
        with st.spinner("CURT AI Assistant querying tools & database..."):
            api_result = call_phase2_api(prompt, st.session_state.phase2_session_id)

        if "error" in api_result:
            reply_text = f"{api_result['error']}"
            provider = None
            tools_used = []
            follow_ups_p2 = [
                "How many brake pads do we have?",
                "Which items are low in stock?",
                "Where is the ECU stored?",
            ]
        else:
            reply_text = api_result.get("response", "No response received.")
            provider = api_result.get("provider")
            tools_used = api_result.get("tools_used", [])
            returned_sid = api_result.get("session_id", st.session_state.phase2_session_id)
            st.session_state.phase2_session_id = returned_sid
            st.session_state.session_id = returned_sid

            if returned_sid not in st.session_state.phase2_known_sessions:
                st.session_state.phase2_known_sessions.insert(0, returned_sid)

            follow_ups_p2 = generate_phase2_followups(reply_text, prompt)
            if not follow_ups_p2:
                follow_ups_p2 = [
                    "Check ECU stock and flag if low.",
                    "What parts are stored in the Mechanical Workshop?",
                    "Which items are currently low in stock?",
                ]

        active_msgs.append(
            {
                "role": "assistant",
                "content": reply_text,
                "provider": provider,
                "tools_used": tools_used,
                "follow_ups": follow_ups_p2,
                "mode": PHASE_2_MODE,
            }
        )


def render_intro() -> None:
    """Render clean, card-style prompt starters with no icons and auto-wrapping text."""
    if _messages():
        return

    is_phase1 = st.session_state.selected_mode == PHASE_1_MODE
    intro_title = (
        "Phase 1: Deterministic Heuristic Assistant"
        if is_phase1
        else "Phase 2: LLM Agent & Function Calling"
    )
    intro_sub = (
        "Fast rule-based inventory assistant. Test exact stock, locations, category queries, and typos without external APIs."
        if is_phase1
        else "Autonomous LLM assistant with multi-turn conversation memory, schema-validated database tools, and shortage flagging."
    )
    badge_label = "RULE-BASED" if is_phase1 else "LLM AGENT"

    st.markdown(
        f"""
        <div class="curt-header-container">
            <div>
                <h3 style="margin: 0; padding: 0; font-size: 1.15rem; font-weight: 700;">{intro_title}</h3>
                <div style="font-size: 0.85rem; opacity: 0.75; margin-top: 0.2rem;">{intro_sub}</div>
            </div>
            <div>
                <span class="curt-badge-red">{badge_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    prompts = QUICK_PROMPTS_PHASE1 if is_phase1 else QUICK_PROMPTS_PHASE2

    st.markdown(
        "<div style='font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.75; margin-bottom: 0.65rem;'>Suggested Inquiries — Click any card to ask instantly:</div>",
        unsafe_allow_html=True,
    )

    # 2-column grid of compact, multi-line prompt cards without icons
    st.markdown('<div class="prompt-grid-container">', unsafe_allow_html=True)
    cols = st.columns(2)
    for idx, (title, query) in enumerate(prompts):
        with cols[idx % 2]:
            # Styled with markdown: Bold Title on line 1, Query on line 2 in muted italics
            label = f"**{title}**\n\n_{query}_"
            if st.button(
                label,
                key=f"intro_prompt_{idx}",
                use_container_width=True,
                help=f"Ask: {query}",
            ):
                st.session_state.pending_prompt = query
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_chat_history() -> None:
    """Render dialogue messages without duplicate headers, with clean tool disclosures."""
    msgs = _messages()
    latest_index = len(msgs) - 1

    for idx, msg in enumerate(msgs):
        role = msg["role"]
        with st.chat_message(role, avatar="🏎️" if role == "assistant" else "👤"):
            if role == "user":
                st.markdown(msg["content"])
            else:
                msg_mode = msg.get("mode", PHASE_1_MODE)
                is_p1 = msg_mode == PHASE_1_MODE
                engine_badge = (
                    '<span class="curt-badge-gray">Phase 1 · Rule-Based</span>'
                    if is_p1
                    else '<span class="curt-badge-red">Phase 2 · LLM Agent</span>'
                )
                provider = msg.get("provider")
                provider_tag = f'<span class="curt-badge-gray" style="font-size: 0.72rem;">Model: <b>{provider}</b></span>' if provider else ""

                st.markdown(
                    f"""
                    <div class="assistant-meta-bar">
                        {engine_badge}
                        {provider_tag}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(msg["content"])

                # Render tool calls if Phase 2 executed tools (collapsible disclosure)
                tools = msg.get("tools_used", [])
                if tools:
                    tools_tags = " ".join(f'<span class="curt-badge-tool"><code>{t}</code></span>' for t in tools)
                    st.markdown(
                        f"""
                        <details class="curt-tools-disclosure">
                            <summary>
                                <span class="disclosure-arrow">▶</span>
                                <span>Tools Executed</span>
                                <span class="curt-tools-count">{len(tools)}</span>
                            </summary>
                            <div class="curt-tools-body">
                                {tools_tags}
                            </div>
                        </details>
                        """,
                        unsafe_allow_html=True,
                    )

            # Follow-up questions (rendered only on the latest assistant response)
            follow_ups = msg.get("follow_ups", [])
            if role == "assistant" and idx == latest_index and follow_ups:
                st.markdown(
                    """
                    <div class="followup-container">
                        <div class="followup-heading">Suggested Follow-Up Inquiries</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                chip_cols = st.columns(len(follow_ups))
                for f_idx, follow_up in enumerate(follow_ups):
                    with chip_cols[f_idx]:
                        if st.button(
                            follow_up,
                            key=f"chip_{idx}_{f_idx}",
                            use_container_width=True,
                            help=f"Ask: {follow_up}",
                        ):
                            st.session_state.pending_prompt = follow_up
                            st.rerun()


def render_inventory_tab() -> None:
    """Render full-width inventory telemetry, search filters, and live table."""
    parts = get_all_parts()
    if not parts:
        st.info("Inventory table is empty.")
        return

    inventory_df = pd.DataFrame(parts)
    total_parts = len(inventory_df)
    total_units = int(inventory_df["quantity"].sum())
    low_stock_parts = int((inventory_df["quantity"] <= DEFAULT_LOW_STOCK_THRESHOLD).sum())
    healthy_parts = total_parts - low_stock_parts

    # High-impact telemetry metrics cards
    st.markdown(
        f"""
        <div class="curt-telemetry-row">
            <div class="telemetry-card">
                <div class="telemetry-card-title">Part Types</div>
                <div class="telemetry-card-val">{total_parts}</div>
                <div class="telemetry-card-sub">Cataloged SKU classifications</div>
            </div>
            <div class="telemetry-card">
                <div class="telemetry-card-title">Total Units In Stock</div>
                <div class="telemetry-card-val">{total_units}</div>
                <div class="telemetry-card-sub">Aggregated inventory count</div>
            </div>
            <div class="telemetry-card {'alert' if low_stock_parts > 0 else ''}">
                <div class="telemetry-card-title" style="color: {'#dc3545' if low_stock_parts > 0 else 'inherit'};">
                    Low Stock Alerts (≤ {DEFAULT_LOW_STOCK_THRESHOLD})
                </div>
                <div class="telemetry-card-val" style="color: {'#dc3545' if low_stock_parts > 0 else 'inherit'};">
                    {low_stock_parts}
                </div>
                <div class="telemetry-card-sub">Components requiring reorder</div>
            </div>
            <div class="telemetry-card">
                <div class="telemetry-card-title">Healthy Inventory</div>
                <div class="telemetry-card-val" style="color: #28a745;">{healthy_parts}</div>
                <div class="telemetry-card-sub">Components with surplus stock</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3-column filter toolbar
    f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
    with f_col1:
        search_term = st.text_input(
            "Search parts, categories, or storage locations",
            value=st.session_state.filter_search,
            placeholder="e.g. Brake Pads, Workshop, Electronics, ECU...",
            label_visibility="collapsed",
        )
        st.session_state.filter_search = search_term

    with f_col2:
        categories = [CATEGORIES_ALL] + sorted(list({p["category"] for p in parts}))
        selected_cat = st.selectbox(
            "Filter Category",
            categories,
            index=categories.index(st.session_state.filter_category)
            if st.session_state.filter_category in categories
            else 0,
            label_visibility="collapsed",
        )
        st.session_state.filter_category = selected_cat

    with f_col3:
        stock_options = [STOCK_ALL, STOCK_LOW, STOCK_HEALTHY]
        selected_stock = st.selectbox(
            "Filter Stock Level",
            stock_options,
            index=stock_options.index(st.session_state.filter_stock)
            if st.session_state.filter_stock in stock_options
            else 0,
            label_visibility="collapsed",
        )
        st.session_state.filter_stock = selected_stock

    filtered_df = filter_inventory(
        parts,
        st.session_state.filter_search,
        st.session_state.filter_category,
        st.session_state.filter_stock,
    )

    # Action bar and caption
    act_col1, act_col2 = st.columns([3, 1])
    with act_col1:
        st.caption(f"Displaying **{len(filtered_df)}** of **{total_parts}** cataloged items")
    with act_col2:
        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export CSV",
            csv_data,
            "curt_inventory.csv",
            "text/csv",
            use_container_width=True,
        )

    # Full-width interactive dataframe
    st.dataframe(
        filtered_df[["name", "quantity", "category", "location"]],
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Part Name", width="medium"),
            "quantity": st.column_config.NumberColumn("Quantity (Units)", width="small"),
            "category": st.column_config.TextColumn("Category", width="medium"),
            "location": st.column_config.TextColumn("Storage Location", width="large"),
        },
        use_container_width=True,
        height=380,
    )


def main() -> None:
    """Main application execution pipeline."""
    inject_custom_styles()
    init_session_state()
    render_sidebar()

    # Top Navigation Banner with Obvious Mode Switcher & Live Health Status
    head_col, mode_col = st.columns([3, 2])
    p1_active = st.session_state.selected_mode == PHASE_1_MODE
    with head_col:
        st.markdown(
            """
            <div style="margin-bottom: 0.15rem;">
                <h1 style="margin: 0; padding: 0; font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em;">
                    🏎️ CURT Inventory Assistant
                </h1>
                <div style="font-size: 0.82rem; opacity: 0.72; margin-top: 0.1rem;">
                    Cairo University Racing Team · Intelligent Workshop Inventory
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with mode_col:
        is_healthy = check_backend_health()
        status_text = "READY / LIVE" if is_healthy else "OFFLINE"
        status_class = "curt-status-live" if is_healthy else "curt-status-offline"
        pulse_class = "live" if is_healthy else "offline"

        st.markdown(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.25rem;">
                <span style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.7;">
                    Active Engine
                </span>
                <span class="{status_class}">
                    <span class="pulse-indicator {pulse_class}"></span>
                    <b>FastAPI {status_text}</b>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(
                "Rule-Based (P1)" + (" (Active)" if p1_active else ""),
                key="top_btn_p1",
                type="primary" if p1_active else "secondary",
                use_container_width=True,
            ):
                if not p1_active:
                    st.session_state.selected_mode = PHASE_1_MODE
                    st.rerun()
        with col_btn2:
            p2_active = not p1_active
            if st.button(
                "AI Agent (P2)" + (" (Active)" if p2_active else ""),
                key="top_btn_p2",
                type="primary" if p2_active else "secondary",
                use_container_width=True,
            ):
                if not p2_active:
                    st.session_state.selected_mode = PHASE_2_MODE
                    st.rerun()

    # Main Tabs: Assistant Chat vs Full-Width Live Inventory
    tab_chat, tab_inventory = st.tabs(["💬 Assistant Chat", "📦 Live Inventory & Telemetry"])

    with tab_chat:
        # Process pending button clicks (prompt cards or follow-up chips)
        active_prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
        if active_prompt:
            submit_prompt(active_prompt)

        render_intro()
        render_chat_history()

        # Chat Input Box - positioned directly under the last message
        placeholder_text = (
            "Ask about inventory (e.g. 'How many brake pads do we have left?', 'Where is the ECU?')..."
            if p1_active
            else "Ask naturally in Phase 2 (e.g. 'Can you check if we have enough brake pads and where they are?')..."
        )
        user_input = st.chat_input(placeholder_text)
        if user_input:
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_input)
            submit_prompt(user_input)
            st.rerun()

    with tab_inventory:
        render_inventory_tab()


main()
