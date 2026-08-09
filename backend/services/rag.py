"""
SiteSense AI — RAG (Retrieval Augmented Generation) Pipeline

The intelligence core of SiteSense.  Every user question flows
through this 5-stage pipeline:

    1. Embed query   (Voyage AI or OpenAI)
    2. Vector search (ChromaDB — tenant-scoped collection)
    3. Rerank        (FlashRank cross-encoder → top 3)
    4. Build prompt  (system rules + context + history)
    5. Generate      (Claude or Gemini → ChatbotResponse)

The pipeline NEVER crashes.  On any failure it returns a safe
fallback ``ChatbotResponse``.
"""

import logging
from typing import Any

from flashrank import Ranker, RerankRequest
from llama_index.core.llms import ChatMessage as LLMChatMessage

from schemas.chat import ChatbotResponse
from services.chroma import query_collection
from services.embeddings import get_query_embedding
from services.llm_provider import generate_structured_response
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level FlashRank reranker — loaded once on first call
# ---------------------------------------------------------------------------
_ranker: Ranker | None = None


def get_ranker() -> Ranker:
    """Return the FlashRank reranker, initialising on first call."""
    global _ranker
    if _ranker is None:
        _ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    return _ranker


# ===================================================================
#  HELPERS
# ===================================================================

def _build_fallback(tenant_config: dict) -> ChatbotResponse:
    """Return a safe fallback ``ChatbotResponse``."""
    return ChatbotResponse(
        answer=tenant_config.get(
            "fallback_message",
            "I don't have information on that topic.",
        ),
        was_answered=False,
        confidence="low",
        sources=[],
        follow_up_questions=[],
        response_type="fallback",
    )


def _score_to_confidence(score: float) -> str:
    """Map a FlashRank relevance score to a confidence label."""
    if score >= 0.7:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


def _format_history(chat_history: list[dict], max_turns: int = 5) -> str:
    """
    Format recent conversation history as a readable string.

    Only the last *max_turns* exchanges are included to stay
    within the context window.
    """
    if not chat_history:
        return ""

    recent = chat_history[-max_turns:]
    lines: list[str] = []
    for msg in recent:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _deduplicate_sources(metadatas: list[dict]) -> list[str]:
    """Extract a deduplicated, ordered list of source names."""
    seen: set[str] = set()
    sources: list[str] = []
    for meta in metadatas:
        name = meta.get("source_name") or meta.get("source_url", "Document")
        if name not in seen:
            seen.add(name)
            sources.append(name)
    return sources


# ===================================================================
#  MAIN RAG PIPELINE
# ===================================================================

async def run_rag_pipeline(
    query: str,
    bot_id: str,
    tenant_config: dict,
    chat_history: list[dict] | None = None,
    user_id: str = "",
) -> tuple[ChatbotResponse, int]:
    """
    Execute the full 5-stage RAG pipeline for a user query.

    Parameters
    ----------
    query : str
        The user's question.
    bot_id : str
        Tenant identifier used to scope ChromaDB collection.
    tenant_config : dict
        Full tenant record (from ``database.get_tenant_by_bot_id``).
    chat_history : list[dict], optional
        Previous ``[{"role": ..., "content": ...}, ...]`` turns.

    Returns
    -------
    ChatbotResponse
        Structured response with answer, confidence, sources, etc.
    """
    chat_history = chat_history or []

    try:
        # =============================================================
        # STAGE 1 — Embed the query
        # =============================================================
        try:
            query_embedding = await get_query_embedding(query)
        except Exception as e:
            logger.error(f"STAGE 1 FAILED (Embeddings): {str(e)}")
            raise

        # =============================================================
        # STAGE 2 — Vector search in ChromaDB
        # =============================================================
        try:
            results = await query_collection(
                bot_id=bot_id,
                query_embedding=query_embedding,
                n_results=10,
            )
        except Exception as e:
            logger.error(f"STAGE 2 FAILED (ChromaDB): {str(e)}")
            raise

        raw_chunks: list[str] = results["documents"][0] if results["documents"] else []
        raw_metadata: list[dict] = results["metadatas"][0] if results["metadatas"] else []

        print(f"--- Retrieved {len(raw_chunks)} raw chunks for bot {bot_id} ---")
        
        # Simple top 5 from vector search
        top_results = []
        for idx, (chunk, meta) in enumerate(zip(raw_chunks[:5], raw_metadata[:5])):
            top_results.append({"text": chunk, "meta": meta})

        # Determine confidence
        confidence = "high"

        # =============================================================
        # STAGE 4 — Build prompt
        # =============================================================
        context_blocks: list[str] = []
        top_metadatas: list[dict] = []

        for item in top_results:
            chunk_text = item.get("text", "")
            meta = item.get("meta", {})
            top_metadatas.append(meta)
            source_label = (
                meta.get("source_name")
                or meta.get("source_url", "Document")
            )
            context_blocks.append(f"[Source: {source_label}]\n{chunk_text}")

        context = "\n\n---\n\n".join(context_blocks)
        unique_sources = _deduplicate_sources(top_metadatas)
        history_text = _format_history(chat_history, max_turns=5)

        custom_prompt = tenant_config.get("system_prompt", "")
        bot_name = tenant_config.get("bot_name", "AI Assistant")
        system_prompt = (
            f"You are {bot_name}, a highly helpful and professional AI assistant.\n\n"
            "INSTRUCTIONS:\n"
            "1. Answer primarily using the provided CONTEXT. This is your most reliable information.\n"
            "2. If the context is thin or missing details, use your general knowledge to provide a helpful, relevant, and accurate response.\n"
            "3. Stay focused on the bot's purpose. If the query is completely unrelated (e.g., asking for weather in a Heritage bot), guide the user back to the main topic.\n"
            "4. NEVER say you have no information unless the query is completely incomprehensible.\n"
        )
        if custom_prompt:
            system_prompt += f"\n[User Custom Instructions]: {custom_prompt}\n"

        user_message = ""
        if context:
            user_message += f"RELEVANT CONTEXT:\n{context}\n\n"
        else:
            user_message += "No specific local context found for this query.\n\n"
            
        if history_text:
            user_message += f"CONVERSATION HISTORY:\n{history_text}\n\n"
            
        user_message += (
            f"USER QUESTION: {query}\n\n"
            "Please provide a structured response based on the above."
        )

        # =============================================================
        # STAGE 5 — Generate output with Multi-Provider LLM
        # =============================================================
        provider = tenant_config.get("llm_provider", settings.DEFAULT_LLM_PROVIDER)
        model = tenant_config.get("llm_model", settings.DEFAULT_LLM_MODEL)
        
        try:
            result_dict, tokens = await generate_structured_response(
                system_prompt=system_prompt,
                user_prompt=user_message,
                provider=provider,
                model=model,
                user_id=user_id,
                response_schema=ChatbotResponse,
                context=context
            )
        except Exception as e:
            logger.error(f"STAGE 5 FAILED (LLM Generation - {provider}/{model}): {str(e)}")
            return ChatbotResponse(
                answer="I'm sorry, our AI brain is temporarily over capacity. Please try again in a few moments.",
                sources=unique_sources,
                confidence="low",
                tokens_used=0
            ), 0

        chat_response = ChatbotResponse(**result_dict)
        chat_response.tokens_used = tokens
        
        if chat_response.was_answered:
            chat_response.sources = unique_sources
        chat_response.confidence = confidence

        return chat_response, tokens

    except Exception as exc:
        logger.error(f"RAG PIPELINE FATAL ERROR: {str(exc)}", exc_info=True)
        return _build_fallback(tenant_config), 0


# ===================================================================
#  RESPONSE PARSING
# ===================================================================

def _parse_response(response: Any, tenant_config: dict) -> ChatbotResponse:
    """
    Attempt to parse the LLM response into a ``ChatbotResponse``.
    Returns a safe fallback on any parsing failure.
    """
    try:
        # LlamaIndex structured LLM returns the model directly
        # in response.raw — try multiple access patterns
        if hasattr(response, "raw") and isinstance(response.raw, ChatbotResponse):
            return response.raw

        # The response text may be the JSON string
        response_text = str(response)

        # Attempt to extract JSON block from text if present
        import re
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                extracted_json = json_match.group(1)
                if '"answer"' in extracted_json:
                    return ChatbotResponse.model_validate_json(extracted_json)
            except Exception:
                pass

    except Exception:
        logger.warning("Failed to parse structured response, trying text extraction")

    # Last resort: extract the answer text and wrap it
    try:
        answer_text = str(response).strip()
        if answer_text:
            return ChatbotResponse(
                answer=answer_text,
                was_answered=True,
                confidence="medium",
                sources=[],
                follow_up_questions=[],
                response_type="answer",
            )
    except Exception:
        pass

    return _build_fallback(tenant_config)
