"""Pydantic request and response models for CURT FastAPI routes."""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Payload accepted by the conversational endpoint."""

    message: str = Field(min_length=1, max_length=2_000)
    session_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    """LLM answer and session details returned to the frontend."""

    session_id: str
    response: str
    provider: str
    tools_used: list[str]


class InventoryItem(BaseModel):
    """One database-backed inventory record exposed by the API."""

    id: int
    name: str
    quantity: int
    category: str
    location: str


class HealthResponse(BaseModel):
    """Small readiness response for local development and deployment checks."""

    status: str
    inventory_ready: bool


JsonObject = dict[str, Any]
