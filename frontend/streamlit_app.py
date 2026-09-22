"""Streamlit frontend for the CURT Inventory Assistant.

Cairo University Racing Team (CURT) Formula Student / FSAE.
Modern, responsive interface supporting:
- Phase 1: Deterministic rule-based assistant
- Phase 2: LLM-powered backend assistant with controlled function calling
"""

import json
import os
import urllib.error
import urllib.request
from uuid import uuid4

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
STOCK_LOW = "⚠️ Low Stock Only (≤ 5)"
STOCK_HEALTHY = "✅ In Stock (> 5)"

QUICK_PROMPTS_PHASE1 = [
    ("🛑 Brake Pads Qty", "How many brake pads do we have?"),
    ("📍 ECU Location", "Where is the ECU?"),
    ("🔧 List Brakes", "List all items in Brakes."),
    ("⚠️ Low Stock", "Which items are low in stock?"),
    ("📦 Full Inventory", "Show all items in inventory."),
]

QUICK_PROMPTS_PHASE2 = [
    ("🛑 Stock & Location", "How many brake pads do we have left, and where are they stored?"),
    ("⚠️ Shortage Flag", "Check the ECU count and flag a shortage if it's running low."),
    ("🔧 Category Breakdown", "List all items in the Brakes category with total count and units."),
    ("📍 Workshop Search", "What parts do we currently have stored in the Mechanical Workshop?"),
    ("📊 Telemetry Summary", "Give me a high-level inventory telemetry summary."),
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
            --curt-bg-subtle: rgba(225, 6, 0, 0.04);
            --border-radius: 12px;
        }

        /* Top Header styling */
        .curt-header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 1.4rem;
            background: linear-gradient(135deg, rgba(225, 6, 0, 0.08) 0%, rgba(20, 20, 25, 0.03) 100%);
            border: 1px solid rgba(225, 6, 0, 0.18);
            border-radius: var(--border-radius);
            margin-bottom: 1.25rem;
        }

        .curt-badge-red {
            display: inline-block;
            background: #E10600;
            color: #FFFFFF !important;
            font-weight: 700;
            font-size: 0.75rem;
            padding: 0.2rem 0.65rem;
            border-radius: 6px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .curt-badge-gray {
            display: inline-block;
            background: rgba(125, 125, 135, 0.18);
            color: inherit;
            font-weight: 600;
            font-size: 0.75rem;
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
        }

        .curt-badge-tool {
            display: inline-block;
            background: rgba(40, 167, 69, 0.15);
            color: #28a745;
            font-weight: 600;
            font-size: 0.75rem;
            padding: 0.15rem 0.55rem;
            border-radius: 6px;
            border: 1px solid rgba(40, 167, 69, 0.3);
            margin-right: 0.35rem;
            margin-top: 0.25rem;
        }

        /* Metric cards */
        [data-testid="stMetricValue"] {
            font-weight: 800 !important;
            letter-spacing: -0.02em;
        }

        /* Sidebar enhancement */
        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(125, 125, 125, 0.15);
        }

        /* Chat bubbles refinement */
        div[data-testid="stChatMessage"] {
            border-radius: var(--border-radius);
            padding: 0.85rem 1rem;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(125, 125, 125, 0.12);
        }

        /* Suggested question chips */
        .stButton>button {
            border-radius: 8px;
            transition: all 0.2s ease-in-out;
        }
        .stButton>button:hover {
            border-color: #E10600 !important;
            color: #E10600 !important;
            transform: translateY(-1px);
        }

        /* Subtitle banner */
        .curt-subtitle {
            font-size: 0.92rem;
            opacity: 0.8;
            margin-top: -0.3rem;
            margin-bottom: 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_backend_url() -> str:
    """Return backend base URL from environment or default to local FastAPI."""
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def init_session_state() -> None:
    """Initialize state variables for the current Streamlit session."""
    # Dedicated message store for Phase 1 (deterministic rule-based)
    st.session_state.setdefault("phase1_messages", [])

    # Dedicated per-session message store for Phase 2 (LLM agent): {session_id: [msg, ...]}
    st.session_state.setdefault("phase2_sessions", {})
    initial_p2_sid = str(uuid4())
    st.session_state.setdefault("phase2_session_id", initial_p2_sid)
    st.session_state.setdefault("session_id", initial_p2_sid)  # alias for backwards compatibility
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
        # Extract JSON array from the response
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


def render_sidebar() -> None:
    """Render the sidebar with phase toggle, metrics, and live searchable table."""
    with st.sidebar:
        # CURT Logo / Brand banner
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 0.8rem;">
                <span class="curt-badge-red" style="font-size: 0.9rem; padding: 0.3rem 0.9rem;">
                    🏎️ CURT RACING
                </span>
                <div style="font-weight: 700; font-size: 1.05rem; margin-top: 0.4rem;">
                    Formula Student Inventory
                </div>
                <div style="font-size: 0.78rem; opacity: 0.7;">Season 26-27 Technical Task</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.header("⚙️ Assistant Mode", divider=True)

        mode_options = [PHASE_1_MODE, PHASE_2_MODE]
        current_index = 0 if st.session_state.selected_mode == PHASE_1_MODE else 1

        selected_mode = st.radio(
            "Select Assistant Engine",
            mode_options,
            index=current_index,
            help="Switch between Phase 1 (deterministic rule-based) and Phase 2 (LLM function calling).",
            label_visibility="collapsed",
        )

        if selected_mode != st.session_state.selected_mode:
            st.session_state.selected_mode = selected_mode
            st.rerun()

        # Engine details card
        if st.session_state.selected_mode == PHASE_1_MODE:
            st.success("🟢 **Phase 1 Active**: Local deterministic rules & exact DB queries. No API keys needed.")
            if st.button("➕ Reset Phase 1 Chat", width="stretch", key="btn_clear_phase1"):
                start_new_chat()
                st.rerun()
        else:
            is_healthy = check_backend_health()
            if is_healthy:
                st.success(f"🟢 **FastAPI Ready** (`{get_backend_url()}`)")
            else:
                st.warning(f"🟠 **FastAPI Unreachable** (`{get_backend_url()}`)")

            # ── Session Management ──────────────────────────────────────────
            st.markdown("**🆔 Phase 2 Session Management**")

            active_sid = st.session_state.phase2_session_id
            st.caption(f"Active Session: `{active_sid[:20]}...`")

            known = st.session_state.get("phase2_known_sessions", [active_sid])
            session_labels = [
                ("▶ " if sid == active_sid else "") + sid[:24] + "..." for sid in known
            ]
            chosen_label = st.selectbox(
                "Switch session",
                session_labels,
                index=0,
                key="session_history_select",
                help="Select a session to switch back to it and see its chat history.",
            )
            chosen_full = known[session_labels.index(chosen_label)]
            if chosen_full != active_sid:
                if st.button("🔄 Switch to this session", width="stretch", key="btn_restore_session"):
                    switch_session(chosen_full)
                    st.rerun()

            if st.button("➕ New Chat Session", width="stretch", key="btn_new_chat_sidebar"):
                start_new_chat()
                st.rerun()

        st.header("📦 Inventory Telemetry", divider=True)

        parts = get_all_parts()
        if not parts:
            st.info("Inventory table is empty.")
            return

        inventory_df = pd.DataFrame(parts)
        total_parts = len(inventory_df)
        total_units = int(inventory_df["quantity"].sum())
        low_stock_parts = int(
            (inventory_df["quantity"] <= DEFAULT_LOW_STOCK_THRESHOLD).sum()
        )

        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Items", total_parts)
        m_col2.metric("Units", total_units)
        m_col3.metric("Low Stock", low_stock_parts)

        # Filters accordion
        with st.expander("🔍 Filter & Search Inventory", expanded=False):
            search_term = st.text_input(
                "Search parts/locations",
                value=st.session_state.filter_search,
                placeholder="e.g. Brake, Lab, Engine...",
            )
            st.session_state.filter_search = search_term

            categories = [CATEGORIES_ALL] + sorted(list({p["category"] for p in parts}))
            selected_cat = st.selectbox(
                "Category",
                categories,
                index=categories.index(st.session_state.filter_category)
                if st.session_state.filter_category in categories
                else 0,
            )
            st.session_state.filter_category = selected_cat

            stock_options = [STOCK_ALL, STOCK_LOW, STOCK_HEALTHY]
            selected_stock = st.selectbox(
                "Stock Status",
                stock_options,
                index=stock_options.index(st.session_state.filter_stock)
                if st.session_state.filter_stock in stock_options
                else 0,
            )
            st.session_state.filter_stock = selected_stock

        filtered_inventory = filter_inventory(
            parts,
            st.session_state.filter_search,
            st.session_state.filter_category,
            st.session_state.filter_stock,
        )

        st.caption(f"Showing **{len(filtered_inventory)}** of {total_parts} part types")
        st.dataframe(
            filtered_inventory[["name", "quantity", "category", "location"]],
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Part Name", width="medium"),
                "quantity": st.column_config.NumberColumn("Qty", width="small"),
                "category": st.column_config.TextColumn("Category", width="small"),
                "location": st.column_config.TextColumn("Storage Location", width="large"),
            },
            height=280,
        )

        # Export & Reset actions
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            csv_data = filtered_inventory.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 CSV Export",
                csv_data,
                "curt_inventory.csv",
                "text/csv",
                width="stretch",
            )
        with action_col2:
            if st.button("➕ New Chat", width="stretch"):
                start_new_chat()
                st.rerun()


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
        with st.spinner("🏎️ CURT AI Assistant querying tools & database..."):
            api_result = call_phase2_api(prompt, st.session_state.phase2_session_id)

        if "error" in api_result:
            reply_text = f"⚠️ {api_result['error']}"
            provider = None
            tools_used = []
            follow_ups_p2 = []
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
    """Render welcoming quick-start cards before user begins chatting."""
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
                <h3 style="margin: 0; padding: 0;">{intro_title}</h3>
                <div class="curt-subtitle">{intro_sub}</div>
            </div>
            <div>
                <span class="curt-badge-red">{badge_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    prompts = QUICK_PROMPTS_PHASE1 if is_phase1 else QUICK_PROMPTS_PHASE2
    st.write("##### 💡 Suggested Questions to Try")
    prompt_cols = st.columns(len(prompts))
    for idx, (label, query) in enumerate(prompts):
        with prompt_cols[idx]:
            if st.button(label, key=f"quick_btn_{idx}", width="stretch"):
                st.session_state.pending_prompt = query
                st.rerun()


def render_chat_history() -> None:
    """Render dialogue messages, engine tags, tool invocations, and suggested replies."""
    msgs = _messages()
    latest_index = len(msgs) - 1

    for idx, msg in enumerate(msgs):
        role = msg["role"]
        with st.chat_message(role, avatar="🏎️" if role == "assistant" else "👤"):
            st.markdown(msg["content"])

            if role == "assistant":
                # Render metadata badges
                badges_html = []
                msg_mode = msg.get("mode")
                if msg_mode:
                    badges_html.append(f'<span class="curt-badge-gray">{msg_mode}</span>')

                provider = msg.get("provider")
                if provider:
                    badges_html.append(f'<span class="curt-badge-gray">Provider: <b>{provider}</b></span>')

                if badges_html:
                    st.markdown(" ".join(badges_html), unsafe_allow_html=True)

                # Render tool calls if Phase 2 used tools
                tools = msg.get("tools_used", [])
                if tools:
                    tools_tags = " ".join(f'<span class="curt-badge-tool">🛠️ {t}</span>' for t in tools)
                    st.markdown(f"<div style='margin-top: 0.35rem;'><b>Tools Executed:</b> {tools_tags}</div>", unsafe_allow_html=True)

            # Suggested follow-up chips (Phase 1 and Phase 2)
            follow_ups = msg.get("follow_ups", [])
            if idx == latest_index and follow_ups:
                msg_mode = msg.get("mode", "")
                chip_label = "💬 **Suggested Follow-Up Questions**" if msg_mode == PHASE_1_MODE else "🤖 **AI-Generated Follow-Up Questions**"
                with st.container(border=True):
                    st.caption(chip_label)
                    chip_cols = st.columns(min(len(follow_ups), 4))
                    for f_idx, follow_up in enumerate(follow_ups):
                        col = chip_cols[f_idx % len(chip_cols)]
                        with col:
                            if st.button(
                                follow_up,
                                key=f"chip_{idx}_{f_idx}",
                                width="stretch",
                            ):
                                st.session_state.pending_prompt = follow_up
                                st.rerun()


def main() -> None:
    """Main application execution pipeline."""
    inject_custom_styles()
    init_session_state()
    render_sidebar()

    # Top Navigation Banner
    is_phase1 = st.session_state.selected_mode == PHASE_1_MODE
    engine_label = "Phase 1: Deterministic Heuristic" if is_phase1 else "Phase 2: LLM + Function Calling"
    engine_badge = '<span class="curt-badge-gray">Rule-Based</span>' if is_phase1 else '<span class="curt-badge-red">LLM Agent</span>'

    st.markdown(
        f"""
        <div style="display: flex; align-items: baseline; justify-content: space-between; border-bottom: 2px solid rgba(225, 6, 0, 0.2); padding-bottom: 0.4rem; margin-bottom: 0.9rem;">
            <div>
                <h1 style="margin: 0; padding: 0; font-size: 1.8rem; font-weight: 800;">
                    🏎️ CURT Inventory Assistant
                </h1>
                <div style="font-size: 0.85rem; opacity: 0.75;">
                    Cairo University Racing Team · Intelligent Workshop Inventory
                </div>
            </div>
            <div style="text-align: right;">
                {engine_badge}
                <div style="font-size: 0.8rem; font-weight: 600; opacity: 0.85; margin-top: 0.2rem;">{engine_label}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_intro()

    # Process pending button clicks
    active_prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

    # Chat Input Box
    placeholder_text = (
        "Ask about inventory (e.g. 'How many brake pads do we have left?', 'Where is the ECU?')..."
        if is_phase1
        else "Ask naturally in Phase 2 (e.g. 'Can you check if we have enough brake pads and where they are?')..."
    )
    user_input = st.chat_input(placeholder_text)
    if user_input:
        active_prompt = user_input

    if active_prompt:
        submit_prompt(active_prompt)

    render_chat_history()


main()
