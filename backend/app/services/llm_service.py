"""Provider adapters and function-calling orchestration for FastAPI Phase 2."""

import json
from dataclasses import dataclass
from typing import Any

from ..core.config import Settings
from .conversation_memory import ConversationMessage, ConversationStore
from ..tools.inventory_tools import (
    GROQ_TOOL_DEFINITIONS,
    INVENTORY_TOOL_DEFINITIONS,
    execute_tool,
)


SYSTEM_PROMPT = """You are the CURT Inventory Assistant. Answer only questions about the
current CURT inventory using the available backend tools. Never invent quantities,
locations, categories, or stock status. Use a tool whenever the user asks about
inventory data. If the request is ambiguous, ask a concise follow-up question.
Use flag_shortage only when the user explicitly asks to flag or alert a shortage.
After receiving tool results, answer clearly and briefly."""
MAX_TOOL_ROUNDS = 6


class LLMConfigurationError(RuntimeError):
    """Raised when the selected provider has not been configured safely."""


@dataclass(frozen=True)
class AssistantReply:
    """A completed provider response and the tools it used."""

    content: str
    provider: str
    tools_used: list[str]


class ChatService:
    """Coordinate provider calls, controlled tools, and in-memory chat history."""

    def __init__(
        self,
        memory: ConversationStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.memory = memory or ConversationStore()
        self.settings = settings or Settings.from_environment()

    def respond(self, session_id: str, user_message: str) -> AssistantReply:
        """Generate an answer and remember the completed conversation turn."""
        provider = self.settings.llm_provider
        history = self.memory.get_history(session_id)

        if provider == "groq":
            reply = self._respond_with_groq(history, user_message)
        elif provider == "gemini":
            reply = self._respond_with_gemini(history, user_message)
        else:
            raise LLMConfigurationError(
                "LLM_PROVIDER must be set to either 'groq' or 'gemini'."
            )

        self.memory.append_turn(session_id, user_message, reply.content)
        return reply

    def _respond_with_groq(
        self, history: list[ConversationMessage], user_message: str
    ) -> AssistantReply:
        api_key = self.settings.groq_api_key
        if not api_key:
            raise LLMConfigurationError("Missing GROQ_API_KEY in the environment.")

        try:
            from groq import Groq
        except ImportError as error:
            raise LLMConfigurationError(
                "Groq support is not installed. Run 'uv sync' to install dependencies."
            ) from error

        client = Groq(api_key=api_key)
        model = self.settings.groq_model
        messages: list[Any] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *({"role": item.role, "content": item.content} for item in history),
            {"role": "user", "content": user_message},
        ]
        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=GROQ_TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0,
            )
            message = completion.choices[0].message
            tool_calls = message.tool_calls or []
            if not tool_calls:
                return AssistantReply(
                    content=message.content or "I could not generate an inventory answer.",
                    provider="groq",
                    tools_used=tools_used,
                )

            messages.append(message)
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tools_used.append(tool_name)
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                result = execute_tool(tool_name, arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(result),
                    }
                )

        raise RuntimeError("The model exceeded the maximum number of tool-call rounds.")

    def _respond_with_gemini(
        self, history: list[ConversationMessage], user_message: str
    ) -> AssistantReply:
        api_key = self.settings.gemini_api_key
        if not api_key:
            raise LLMConfigurationError("Missing GEMINI_API_KEY in the environment.")

        try:
            from google import genai
        except ImportError as error:
            raise LLMConfigurationError(
                "Gemini support is not installed. Run 'uv sync' to install dependencies."
            ) from error

        client = genai.Client(api_key=api_key)
        model = self.settings.gemini_model
        conversation = "\n".join(
            f"{message.role.title()}: {message.content}" for message in history
        )
        prompt = (
            f"{SYSTEM_PROMPT}\n\nConversation so far:\n{conversation or '(new session)'}"
            f"\nUser: {user_message}"
        )
        interaction = client.interactions.create(
            model=model,
            input=prompt,
            tools=INVENTORY_TOOL_DEFINITIONS,
        )
        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            function_calls = [
                step for step in interaction.steps if step.type == "function_call"
            ]
            if not function_calls:
                return AssistantReply(
                    content=interaction.output_text
                    or "I could not generate an inventory answer.",
                    provider="gemini",
                    tools_used=tools_used,
                )

            tool_results = []
            for function_call in function_calls:
                tool_name = function_call.name
                tools_used.append(tool_name)
                result = execute_tool(tool_name, dict(function_call.arguments or {}))
                tool_results.append(
                    {
                        "type": "function_result",
                        "name": tool_name,
                        "call_id": function_call.id,
                        "result": [{"type": "text", "text": json.dumps(result)}],
                    }
                )

            interaction = client.interactions.create(
                model=model,
                previous_interaction_id=interaction.id,
                input=tool_results,
                tools=INVENTORY_TOOL_DEFINITIONS,
            )

        raise RuntimeError("The model exceeded the maximum number of tool-call rounds.")
