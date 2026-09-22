"""
db.py

Data-access layer for the CURT inventory database.
Handles SQLite connection management, table initialization, seeding, and CRUD operations.
Both Phase 1 and Phase 2 assistant modules interface with this layer.
"""

import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_PATH = Path(os.getenv("CURT_DB_PATH", "curt_inventory.db")).resolve()

SEED_PARTS = [
    ("Brake Pads", 12, "Brakes", "Mechanical Workshop"),
    ("Brake Discs", 6, "Brakes", "Mechanical Workshop"),
    ("ECU", 2, "Electronics", "Electronics Lab, Shelf B"),
    ("Wiring Harness", 4, "Electronics", "Electronics Lab, Shelf A"),
    ("Carbon Fiber Sheet", 15, "Chassis", "Composites Room"),
    ("Suspension Spring", 8, "Suspension", "Mechanical Workshop"),
    ("Steering Wheel", 1, "Cockpit", "Cockpit Storage"),
    ("Battery Pack", 3, "Electronics", "Electronics Lab, Shelf C"),
    ("Radiator", 2, "Cooling", "Cooling Systems Rack"),
    ("Tire Set (Slick)", 4, "Tires", "Tire Storage Room"),
    ("Fuel Injector", 6, "Engine", "Engine Bay Storage"),
]


# ============================================================
# CONNECTION MANAGEMENT
# ============================================================

def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with dict-like row access."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session():
    """Context manager for automatic connection closing and commit handling."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# ============================================================
# INITIALIZATION / SEEDING
# ============================================================

def init_db() -> None:
    """Create the parts table and populate initial seed data if empty."""
    with db_session() as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    location TEXT NOT NULL
                )
                """
            )
            count = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
            if count == 0:
                conn.executemany(
                    """
                    INSERT INTO parts (name, quantity, category, location)
                    VALUES (?, ?, ?, ?)
                    """,
                    SEED_PARTS,
                )


# ============================================================
# READ OPERATIONS
# ============================================================

def get_all_parts() -> List[Dict[str, Any]]:
    """Return the complete inventory as a list of dictionaries ordered by id."""
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM parts ORDER BY id").fetchall()
        return [dict(row) for row in rows]


def get_part(name: str) -> Optional[Dict[str, Any]]:
    """
    Find a part using a case-insensitive substring match.
    Prioritizes exact match, then shortest matching name.
    """
    if not name or not name.strip():
        return None

    cleaned_name = name.lower().strip()
    query = """
        SELECT *
        FROM parts
        WHERE LOWER(name) LIKE ?
        ORDER BY
            CASE
                WHEN LOWER(name) = LOWER(?) THEN 0
                ELSE 1
            END,
            LENGTH(name)
        LIMIT 1
    """
    with db_session() as conn:
        row = conn.execute(query, (f"%{cleaned_name}%", cleaned_name)).fetchone()
        return dict(row) if row else None


def get_by_category(category: str) -> List[Dict[str, Any]]:
    """Return all parts belonging to a category using case-insensitive substring match."""
    if not category or not category.strip():
        return []

    cleaned_category = category.lower().strip()
    query = """
        SELECT *
        FROM parts
        WHERE LOWER(category) LIKE ?
        ORDER BY name
    """
    with db_session() as conn:
        rows = conn.execute(query, (f"%{cleaned_category}%",)).fetchall()
        return [dict(row) for row in rows]


def get_all_part_names() -> List[str]:
    """Return all inventory part names in alphabetical order."""
    with db_session() as conn:
        rows = conn.execute("SELECT name FROM parts ORDER BY name").fetchall()
        return [row["name"] for row in rows]


def get_all_categories() -> List[str]:
    """Return all unique inventory categories in alphabetical order."""
    with db_session() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM parts ORDER BY category").fetchall()
        return [row["category"] for row in rows]


def get_by_location(location: str) -> List[Dict[str, Any]]:
    """Return all parts stored in a given location using case-insensitive substring match."""
    if not location or not location.strip():
        return []

    cleaned_location = location.lower().strip()
    query = """
        SELECT *
        FROM parts
        WHERE LOWER(location) LIKE ?
        ORDER BY name
    """
    with db_session() as conn:
        rows = conn.execute(query, (f"%{cleaned_location}%",)).fetchall()
        return [dict(row) for row in rows]


def get_all_locations() -> List[str]:
    """Return all unique inventory storage locations in alphabetical order."""
    with db_session() as conn:
        rows = conn.execute("SELECT DISTINCT location FROM parts ORDER BY location").fetchall()
        return [row["location"] for row in rows]


# ============================================================
# UPDATE OPERATIONS
# ============================================================

def update_quantity(name: str, delta: int) -> bool:
    """
    Increase or decrease an item's quantity by delta.
    Returns True if an item was updated, otherwise False.
    """
    if not name or not name.strip():
        return False

    cleaned_name = name.lower().strip()
    query = """
        UPDATE parts
        SET quantity = quantity + ?
        WHERE LOWER(name) LIKE ?
    """
    with db_session() as conn:
        with conn:
            cursor = conn.execute(query, (delta, f"%{cleaned_name}%"))
            return cursor.rowcount > 0
