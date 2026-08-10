"""
SiteSense AI — Ollama Setup & Embedding Service

Configures LlamaIndex to use Ollama for both LLM generation
(mistral) and embedding (nomic-embed-text).

All other services import ``get_llm()`` and
``get_embed_model()`` from this module — they never
instantiate Ollama objects directly.
"""

import logging
from typing import Type

import httpx
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons — lazy-initialised
# ---------------------------------------------------------------------------
_llm: Ollama | None = None
_embed_model: OllamaEmbedding | None = None


# ===================================================================
#  CORE CONFIGURATION
# ===================================================================

def configure_ollama() -> tuple[Ollama, OllamaEmbedding]:
    """
    Instantiate the Ollama LLM and embedding model, then
    register them as the LlamaIndex global defaults.

    Returns
    -------
    tuple[Ollama, OllamaEmbedding]
        ``(llm, embed_model)``
    """
    global _llm, _embed_model

    # -- LLM --
    _llm = Ollama(
        model=settings.OLLAMA_LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        request_timeout=1200.0,  # Increased for stability on slower CPUs (20 mins)
        context_window=8192,
        additional_kwargs={"temperature": 0.1},
    )

    # -- Embedding --
    _embed_model = OllamaEmbedding(
        model_name=settings.OLLAMA_EMBED_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        request_timeout=120.0,
    )

    # -- LlamaIndex global settings --
    LlamaSettings.chunk_size = 512
    LlamaSettings.chunk_overlap = 50

    logger.info(
        "Ollama configured — LLM: %s, Embed: %s @ %s",
        settings.OLLAMA_LLM_MODEL,
        settings.OLLAMA_EMBED_MODEL,
        settings.OLLAMA_BASE_URL,
    )

    return _llm, _embed_model


# ===================================================================
#  ACCESSORS (lazy init)
# ===================================================================

def get_llm() -> Ollama:
    """Return the configured LLM, initialising on first call."""
    global _llm
    if _llm is None:
        configure_ollama()
    return _llm  # type: ignore[return-value]


def get_embed_model() -> OllamaEmbedding:
    """Return the configured embedding model, initialising on first call."""
    global _embed_model
    if _embed_model is None:
        configure_ollama()
    return _embed_model  # type: ignore[return-value]


# ===================================================================
#  STRUCTURED OUTPUT
# ===================================================================

def get_structured_llm(response_schema: Type):
    """
    Return an LLM wrapper that forces JSON output
    conforming to *response_schema* (a Pydantic model).

    Used by the RAG pipeline for structured answers.
    """
    llm = get_llm()
    return llm.as_structured_llm(response_schema)


# ===================================================================
#  EMBEDDING HELPERS
# ===================================================================

async def get_embedding(text: str) -> list[float]:
    """
    Embed a single text string and return the vector.

    Used at **query time** to embed the user's question
    before searching ChromaDB.
    """
    embed_model = get_embed_model()
    embedding = await embed_model.aget_query_embedding(text)
    return embedding


async def get_embeddings_batch(
    texts: list[str],
) -> list[list[float]]:
    """
    Embed multiple texts (used during **ingestion**).

    Processes in batches of 32 to avoid Ollama timeouts
    on large document sets.

    Returns
    -------
    list[list[float]]
        One embedding vector per input text.
    """
    if not texts:
        return []

    embed_model = get_embed_model()
    all_embeddings: list[list[float]] = []
    batch_size = 32

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        batch_embeddings = await embed_model.aget_text_embedding_batch(batch)
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


# ===================================================================
#  HEALTH CHECK
# ===================================================================

async def verify_ollama_connection() -> dict:
    """
    Probe Ollama to confirm it is running and the required
    models are available.

    Called during FastAPI startup.  Logs a **warning** —
    never crashes the server — if Ollama is unreachable.

    Returns
    -------
    dict
        ``{"status", "llm_model", "embed_model", "message"}``
    """
    result = {
        "status": "error",
        "llm_model": settings.OLLAMA_LLM_MODEL,
        "embed_model": settings.OLLAMA_EMBED_MODEL,
        "message": "",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Check Ollama is alive
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()

            available_models = [
                m.get("name", "").split(":")[0]
                for m in data.get("models", [])
            ]

            # 2. Check required models are pulled
            missing: list[str] = []
            for model_name in (
                settings.OLLAMA_LLM_MODEL,
                settings.OLLAMA_EMBED_MODEL,
            ):
                if model_name not in available_models:
                    missing.append(model_name)

            if missing:
                msg = (
                    f"Ollama is running but missing models: "
                    f"{', '.join(missing)}. "
                    f"Run: ollama pull <model> for each."
                )
                logger.warning(msg)
                result["status"] = "warning"
                result["message"] = msg
            else:
                msg = (
                    f"Ollama OK — LLM: {settings.OLLAMA_LLM_MODEL}, "
                    f"Embed: {settings.OLLAMA_EMBED_MODEL}"
                )
                logger.info(msg)
                result["status"] = "ok"
                result["message"] = msg

    except httpx.ConnectError:
        msg = (
            f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}. "
            "Make sure Ollama is running: ollama serve"
        )
        logger.warning(msg)
        result["message"] = msg

    except Exception as exc:
        msg = f"Ollama health-check failed: {exc}"
        logger.warning(msg)
        result["message"] = msg

    return result
