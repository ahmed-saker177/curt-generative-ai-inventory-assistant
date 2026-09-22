"""Environment-backed configuration for the FastAPI service."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded once when an application service is created."""

    llm_provider: str
    groq_api_key: str | None
    groq_model: str
    gemini_api_key: str | None
    gemini_model: str

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load local development variables without overriding deployed settings."""
        load_dotenv(override=True)
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower(),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
        )
