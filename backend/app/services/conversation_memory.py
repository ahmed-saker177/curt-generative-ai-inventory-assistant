"""In-memory conversation storage for Phase 2 FastAPI chat sessions."""

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationMessage:
    """A user or assistant message retained for one chat session."""

    role: str
    content: str


class ConversationStore:
    """Store short chat histories by session ID for the running API process."""

    def __init__(self, max_messages_per_session: int = 100) -> None:
        self._sessions: dict[str, list[ConversationMessage]] = defaultdict(list)
        self._max_messages_per_session = max_messages_per_session

    def get_history(self, session_id: str) -> list[ConversationMessage]:
        """Return a copy of the history so callers cannot mutate stored messages."""
        return list(self._sessions[session_id])

    def append_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        """Add one completed user/assistant exchange and retain a bounded history."""
        messages = self._sessions[session_id]
        messages.extend(
            [
                ConversationMessage(role="user", content=user_message),
                ConversationMessage(role="assistant", content=assistant_message),
            ]
        )
        if len(messages) > self._max_messages_per_session:
            del messages[: len(messages) - self._max_messages_per_session]

    def clear(self, session_id: str) -> None:
        """Remove all messages for one session."""
        self._sessions.pop(session_id, None)
