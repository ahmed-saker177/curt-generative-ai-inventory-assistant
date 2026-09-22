"""Application factory and router registration for the CURT FastAPI backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import chat, health, inventory
from .data.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize the shared SQLite database when the API starts."""
    init_db()
    yield


app = FastAPI(
    title="CURT Inventory Assistant API",
    version="0.2.0",
    description="Phase 2 LLM inventory assistant with controlled function calling.",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(inventory.router)
app.include_router(chat.router)
