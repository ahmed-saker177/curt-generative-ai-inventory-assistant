"""Operational health route."""

from fastapi import APIRouter

from ...schemas.models import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report whether the backend and SQLite inventory are ready."""
    return HealthResponse(status="ok", inventory_ready=True)
