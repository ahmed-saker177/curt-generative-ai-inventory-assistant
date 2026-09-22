"""Conversation routes backed by the selected LLM provider."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from ...schemas.models import ChatRequest, ChatResponse
from ...services.llm_service import ChatService, LLMConfigurationError


router = APIRouter(prefix="/chat", tags=["chat"])
chat_service = ChatService()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Answer one natural-language inventory question in a persistent session."""
    session_id = request.session_id or str(uuid4())
    try:
        reply = chat_service.respond(session_id, request.message.strip())
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return ChatResponse(
        session_id=session_id,
        response=reply.content,
        provider=reply.provider,
        tools_used=reply.tools_used,
    )
