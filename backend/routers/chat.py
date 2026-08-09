"""
SiteSense AI — Chat Router

The public-facing endpoint hit by the embeddable widget.
Runs the full RAG pipeline and logs the conversation.
Now secured via widget_security dependency.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Annotated

import database
from schemas.chat import ChatbotResponse, ChatRequest
from services.rag import run_rag_pipeline
from services.widget_security import verify_widget_request, should_refresh_token

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatbotResponse)
async def chat(
    request_body: ChatRequest,
    widget_data: Annotated[dict, Depends(verify_widget_request)]
):
    """
    Process a chat message through the RAG pipeline.
    Secured via Widget Session JWT.
    """
    tenant = widget_data["tenant"]
    jwt_payload = widget_data["jwt_payload"]
    
    # Run RAG pipeline (returns Response model + tokens used)
    response, tokens = await run_rag_pipeline(
        query=request_body.message,
        bot_id=tenant["bot_id"],
        tenant_config=tenant,
        chat_history=[m.model_dump() for m in request_body.history],
        user_id=tenant.get("user_id", "")
    )
    
    # Log conversation to database (async call)
    try:
        await database.log_conversation(
            tenant_id=tenant["id"],
            session_id=request_body.session_id,
            question=request_body.message,
            answer=response.answer,
            sources_used=response.sources,
            was_answered=response.was_answered,
            confidence=response.confidence,
            response_type=response.response_type,
            tokens_used=tokens,
            llm_provider=tenant.get("llm_provider", "")
        )
    except Exception:
        pass  # Logging failure should never block the response
    
    # Add refresh hint for the widget
    result = response.model_dump()
    result["refresh_token"] = should_refresh_token(jwt_payload)
    
    return result
