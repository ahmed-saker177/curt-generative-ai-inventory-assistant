"""Streamlit frontend for the Phase 1 CURT Inventory Assistant."""

import pandas as pd
import streamlit as st

from db import get_all_parts, init_db
from phase1_assistant import DEFAULT_LOW_STOCK_THRESHOLD, answer_question_with_suggestions


EXAMPLE_QUERIES = [
    "How many brake pads do we have?",
    "Where is the ECU?",
    "List all items in Brakes.",
]


st.set_page_config(
    page_title="CURT Inventory Assistant",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


def init_session_state() -> None:
    """Initialize the chat state for the current Streamlit session."""
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("pending_prompt", None)


def clear_chat_history() -> None:
    """Remove all chat messages from the current session."""
    st.session_state.messages = []
    st.session_state.pending_prompt = None


def filter_inventory(parts: list[dict[str, object]], search_term: str) -> pd.DataFrame:
    """Return inventory rows matching a part name, category, or location."""
    dataframe = pd.DataFrame(parts)
    if not search_term:
        return dataframe

    normalized_search = search_term.strip().lower()
    return dataframe[
        dataframe["name"].str.lower().str.contains(normalized_search, regex=False)
        | dataframe["category"].str.lower().str.contains(normalized_search, regex=False)
        | dataframe["location"].str.lower().str.contains(normalized_search, regex=False)
    ]


def render_sidebar() -> None:
    """Render the live inventory panel and chat controls."""
    with st.sidebar:
        st.header("Inventory overview", divider=True)
        st.caption("Live data from the Phase 1 SQLite database")

        parts = get_all_parts()
        if not parts:
            st.info("Inventory is currently empty.")
            return

        inventory = pd.DataFrame(parts)
        total_parts = len(inventory)
        total_units = int(inventory["quantity"].sum())
        low_stock_parts = int(
            (inventory["quantity"] <= DEFAULT_LOW_STOCK_THRESHOLD).sum()
        )

        metric_columns = st.columns(2)
        metric_columns[0].metric("Part types", total_parts)
        metric_columns[1].metric("Low stock", low_stock_parts)
        st.metric("Total units", total_units)

        search_term = st.text_input(
            "Filter inventory",
            key="inventory_filter",
            placeholder="Search name, category, or location",
        )
        filtered_inventory = filter_inventory(parts, search_term)

        st.caption(f"Showing {len(filtered_inventory)} of {total_parts} part types")
        st.dataframe(
            filtered_inventory[["id", "name", "quantity", "category", "location"]],
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", width="small"),
                "name": st.column_config.TextColumn("Part", width="medium"),
                "quantity": st.column_config.NumberColumn("Qty", width="small"),
                "category": st.column_config.TextColumn("Category", width="medium"),
                "location": st.column_config.TextColumn("Location", width="large"),
            },
        )

        st.divider()
        if st.button("Clear conversation", width="stretch"):
            clear_chat_history()
            st.rerun()


def submit_prompt(prompt: str) -> None:
    """Add a user question and its deterministic inventory answer to history."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    reply_text, follow_ups = answer_question_with_suggestions(prompt)
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": reply_text,
            "follow_ups": follow_ups,
        }
    )


def render_intro() -> None:
    """Render onboarding examples before the user starts a conversation."""
    if st.session_state.messages:
        return

    with st.container(border=True):
        st.subheader("Ask about the inventory")
        st.write(
            "Ask for a quantity, storage location, or category. "
            "Phase 1 answers only from the SQLite inventory database."
        )
        st.caption("Try an example")
        example_columns = st.columns(len(EXAMPLE_QUERIES))
        for index, example_query in enumerate(EXAMPLE_QUERIES):
            with example_columns[index]:
                if st.button(example_query, key=f"example_{index}", width="stretch"):
                    st.session_state.pending_prompt = example_query
                    st.rerun()


def render_chat_history() -> None:
    """Render chat messages and follow-up actions for the latest answer."""
    latest_message_index = len(st.session_state.messages) - 1
    for message_index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            follow_ups = message.get("follow_ups", [])
            if message_index == latest_message_index and follow_ups:
                with st.container(border=True):
                    st.caption("Suggested follow-up questions")
                    for follow_up_index, follow_up in enumerate(follow_ups):
                        if st.button(
                            follow_up,
                            key=f"follow_up_{message_index}_{follow_up_index}",
                            width="content",
                        ):
                            st.session_state.pending_prompt = follow_up
                            st.rerun()


def main() -> None:
    """Run the Phase 1 CURT Inventory Assistant interface."""
    init_session_state()
    render_sidebar()

    st.title("CURT Inventory Assistant")
    st.caption("Phase 1 · Deterministic, rule-based inventory lookup")
    render_intro()

    active_prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    chat_prompt = st.chat_input(
        "Ask about the inventory, for example: How many brake pads do we have?"
    )
    if chat_prompt:
        active_prompt = chat_prompt

    if active_prompt:
        submit_prompt(active_prompt)

    render_chat_history()


if __name__ == "__main__":
    main()
