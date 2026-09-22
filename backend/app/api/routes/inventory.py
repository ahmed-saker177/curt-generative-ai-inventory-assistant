"""Read-only inventory routes."""

from fastapi import APIRouter

from ...data.db import get_all_parts
from ...schemas.models import InventoryItem


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryItem])
def inventory() -> list[dict]:
    """Return the current inventory from the shared SQLite database."""
    return get_all_parts()
