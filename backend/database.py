"""
SiteSense AI — Supabase Database Abstraction Layer

Stage 2 migration to Supabase: Swapping internals to use Supabase 
Python client. Function signatures are updated with user_id for security.
Tables and RLS are managed via supabase/schema.sql.
"""

import json
import random
import string
import uuid
import logging
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import create_async_client, AsyncClient
from config import settings

# ---------------------------------------------------------------------------
# Setup & Initialization
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

_admin_client: AsyncClient | None = None

async def get_admin_client() -> AsyncClient:
    """Lazy initialization of the Supabase admin client (Service Role)."""
    global _admin_client
    if _admin_client is None:
        _admin_client = await create_async_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
    return _admin_client

async def init_db() -> None:
    """Verifies connection to Supabase."""
    client = await get_admin_client()
    try:
        # Just a simple ping to verify service role key & URL
        await client.table("tenants").select("id").limit(1).execute()
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        raise RuntimeError(f"Database connection failed: {e}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_uuid() -> str:
    return str(uuid.uuid4())

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _xor_cipher(data: str, key: str) -> str:
    """Simple XOR cipher for minimal encryption of API keys."""
    if not key:
        key = "default-secret-key"
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

def _encrypt_key(api_key: str) -> str:
    """XOR encrypt and base64 encode."""
    xor_ed = _xor_cipher(api_key, settings.WIDGET_JWT_SECRET)
    return base64.b64encode(xor_ed.encode()).decode()

def _decrypt_key(encrypted_key: str) -> str:
    """Decode base64 and XOR decrypt."""
    decoded = base64.b64decode(encrypted_key.encode()).decode()
    return _xor_cipher(decoded, settings.WIDGET_JWT_SECRET)

# ---------------------------------------------------------------------------
# Tenant Operations
# ---------------------------------------------------------------------------

async def create_tenant(
    user_id: str,
    name: str,
    bot_name: str = "AI Assistant",
    welcome_message: str = "Hi! How can I help you?",
    fallback_message: str = "I don't have information on that topic.",
    primary_color: str = "#2563eb",
    system_prompt: str = "",
    allowed_origins: list[str] | None = None,
    llm_provider: str = "gemini",
    llm_model: str = "gemini-2.0-flash",
    suggested_questions: list[str] | None = None,
) -> dict:
    """Create a new tenant in Supabase."""
    client = await get_admin_client()
    
    # Generate unique bot_id
    bot_id = ""
    while True:
        candidate = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        res = await client.table("tenants").select("bot_id").eq("bot_id", candidate).execute()
        if not res.data:
            bot_id = candidate
            break

    data = {
        "user_id": user_id,
        "name": name,
        "bot_id": bot_id,
        "bot_name": bot_name,
        "welcome_message": welcome_message,
        "fallback_message": fallback_message,
        "primary_color": primary_color,
        "system_prompt": system_prompt,
        "allowed_origins": allowed_origins or [],
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "suggested_questions": suggested_questions or [],
    }

    try:
        result = await client.table("tenants").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        return {}

async def get_all_tenants(user_id: str) -> list[dict]:
    """Return all tenants for a specific user."""
    client = await get_admin_client()
    try:
        result = await client.table("tenants").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Error fetching all tenants: {e}")
        return []

async def get_tenant_by_id(tenant_id: str, user_id: str) -> dict | None:
    """Return a single tenant by ID, verifying ownership."""
    client = await get_admin_client()
    try:
        result = await client.table("tenants").select("*").eq("id", tenant_id).eq("user_id", user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error fetching tenant by ID: {e}")
        return None

async def get_tenant_by_bot_id(bot_id: str) -> dict | None:
    """Public lookup of tenant by bot_id for the widget."""
    client = await get_admin_client()
    try:
        result = await client.table("tenants").select("*").eq("bot_id", bot_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error fetching tenant by bot ID: {e}")
        return None

async def update_tenant(tenant_id: str, user_id: str, updates: dict) -> dict:
    """Update tenant fields, verifying ownership."""
    client = await get_admin_client()
    try:
        result = await client.table("tenants").update(updates).eq("id", tenant_id).eq("user_id", user_id).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error updating tenant: {e}")
        return {}

async def delete_tenant(tenant_id: str, user_id: str) -> bool:
    """Delete a tenant and all its associated data (cascade in DB)."""
    client = await get_admin_client()
    try:
        result = await client.table("tenants").delete().eq("id", tenant_id).eq("user_id", user_id).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Error deleting tenant: {e}")
        return False

# ---------------------------------------------------------------------------
# Source Operations
# ---------------------------------------------------------------------------

async def create_source(
    tenant_id: str,
    type: str,
    name: str,
    location: str,
    file_path: str = "",
) -> dict:
    """Create a new data source for a tenant."""
    client = await get_admin_client()
    data = {
        "tenant_id": tenant_id,
        "type": type,
        "name": name,
        "location": location,
        "file_path": file_path,
        "status": "pending",
    }
    try:
        result = await client.table("sources").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error creating source: {e}")
        return {}

async def get_sources_by_tenant(tenant_id: str) -> list[dict]:
    """Return all sources for a tenant."""
    client = await get_admin_client()
    try:
        result = await client.table("sources").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Error fetching sources: {e}")
        return []

async def get_source_by_id(source_id: str) -> dict | None:
    client = await get_admin_client()
    try:
        result = await client.table("sources").select("*").eq("id", source_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error fetching source: {e}")
        return None

async def update_source_status(
    source_id: str,
    status: str,
    chunk_count: int | None = None,
    content_hash: str | None = None,
    error_message: str | None = None,
) -> dict:
    client = await get_admin_client()
    updates: dict[str, Any] = {"status": status}
    if chunk_count is not None:
        updates["chunk_count"] = chunk_count
    if content_hash is not None:
        updates["content_hash"] = content_hash
    if error_message is not None:
        updates["error_message"] = error_message
    if status == "indexed":
        updates["last_indexed"] = _now_iso()

    try:
        result = await client.table("sources").update(updates).eq("id", source_id).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error updating source status: {e}")
        return {}

async def delete_source(source_id: str) -> bool:
    client = await get_admin_client()
    try:
        result = await client.table("sources").delete().eq("id", source_id).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Error deleting source: {e}")
        return False

# ---------------------------------------------------------------------------
# Conversation Operations
# ---------------------------------------------------------------------------

async def log_conversation(
    tenant_id: str,
    session_id: str,
    question: str,
    answer: str,
    sources_used: list[str] | None = None,
    was_answered: bool = False,
    confidence: str = "low",
    response_type: str = "fallback",
    tokens_used: int = 0,
    llm_provider: str = "",
) -> dict:
    client = await get_admin_client()
    data = {
        "tenant_id": tenant_id,
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "sources_used": sources_used or [],
        "was_answered": was_answered,
        "confidence": confidence,
        "response_type": response_type,
        "tokens_used": tokens_used,
        "llm_provider": llm_provider,
    }
    try:
        result = await client.table("conversations").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error logging conversation: {e}")
        return {}

async def get_conversations_by_tenant(tenant_id: str, limit: int = 50) -> list[dict]:
    client = await get_admin_client()
    try:
        result = await client.table("conversations").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return []

async def get_unanswered_questions(tenant_id: str) -> list[dict]:
    client = await get_admin_client()
    try:
        result = await client.table("conversations").select("*").eq("tenant_id", tenant_id).eq("was_answered", False).order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Error fetching unanswered questions: {e}")
        return []

# ---------------------------------------------------------------------------
# Analytics Operations
# ---------------------------------------------------------------------------

async def get_analytics_summary(tenant_id: str) -> dict:
    """Compute analytics snapshot using multiple queries."""
    client = await get_admin_client()
    
    try:
        # 1. Totals
        res_total = await client.table("conversations").select("was_answered").eq("tenant_id", tenant_id).execute()
        all_convs = res_total.data or []
        total = len(all_convs)
        answered = sum(1 for c in all_convs if c.get("was_answered"))
        unanswered = total - answered
        rate = round((answered / total) * 100, 1) if total > 0 else 0.0

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        res_today = await client.table("conversations").select("id", count="exact").eq("tenant_id", tenant_id).gte("created_at", today_start).execute()
        today_count = res_today.count or 0

        # 3. Tokens & Provider
        res_metrics = await client.table("conversations").select("tokens_used, llm_provider").eq("tenant_id", tenant_id).execute()
        metrics_data = res_metrics.data or []
        total_tokens = sum(row.get("tokens_used", 0) for row in metrics_data)
        
        provider_counts: dict[str, int] = {}
        for row in metrics_data:
            p = row.get("llm_provider")
            if p:
                provider_counts[p] = provider_counts.get(p, 0) + 1
        
        top_provider = max(provider_counts, key=provider_counts.get) if provider_counts else "N/A"

        # 4. Last 7 days
        daily_counts = []
        for i in range(7):
            d = (datetime.now(timezone.utc) - timedelta(days=6-i))
            d_start = d.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            d_end = (d + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            res_d = await client.table("conversations").select("id", count="exact").eq("tenant_id", tenant_id).gte("created_at", d_start).lt("created_at", d_end).execute()
            daily_counts.append({"date": d.strftime("%Y-%m-%d"), "count": res_d.count or 0})

        # 4. Top Sources
        res_sources = await client.table("conversations").select("sources_used").eq("tenant_id", tenant_id).neq("sources_used", "[]").execute()
        source_usage: dict[str, int] = {}
        for row in (res_sources.data or []):
            srcs = row.get("sources_used") or []
            for s in srcs:
                source_usage[s] = source_usage.get(s, 0) + 1
        
        top_sources = sorted([{"name": k, "count": v} for k, v in source_usage.items()], key=lambda x: x["count"], reverse=True)[:10]

        return {
            "total_conversations": total,
            "answered_count": answered,
            "unanswered_count": unanswered,
            "answer_rate": rate,
            "conversations_today": today_count,
            "total_tokens": total_tokens,
            "top_provider": top_provider,
            "top_sources": top_sources,
            "daily_counts": daily_counts,
        }
    except Exception as e:
        logger.error(f"Error gathering analytics: {e}")
        return {}

# ---------------------------------------------------------------------------
# Lead Operations
# ---------------------------------------------------------------------------

async def create_lead(tenant_id: str, session_id: str, name: str = "", email: str = "") -> dict:
    client = await get_admin_client()
    data = {
        "tenant_id": tenant_id,
        "session_id": session_id,
        "name": name,
        "email": email,
    }
    try:
        result = await client.table("leads").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error creating lead: {e}")
        return {}

async def get_leads_by_tenant(tenant_id: str) -> list[dict]:
    client = await get_admin_client()
    try:
        result = await client.table("leads").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return []

# ---------------------------------------------------------------------------
# API Key Operations (NEW)
# ---------------------------------------------------------------------------

DB_PROVIDER_MAP = {
    "claude": "anthropic",
    "openrouter": "openai"
}
REVERSE_PROVIDER_MAP = {
    "anthropic": "claude",
    "openai": "openrouter"
}

async def save_api_key(user_id: str, provider: str, api_key: str) -> dict:
    """Store encrypted API key for a user and provider."""
    client = await get_admin_client()
    
    db_provider = DB_PROVIDER_MAP.get(provider, provider)
    preview = "****" + api_key[-4:] if len(api_key) > 4 else api_key
    encrypted = _encrypt_key(api_key)
    
    # We use manual delete-then-insert since schema doesn't have unique constraint for upsert
    try:
        await client.table("user_api_keys").delete().eq("user_id", user_id).eq("provider", db_provider).execute()
        
        data = {
            "user_id": user_id,
            "provider": db_provider,
            "key_preview": preview,
            "key_encrypted": encrypted,
            "is_active": True,
        }
        result = await client.table("user_api_keys").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error saving API key: {e}")
        return {}

async def get_api_key(user_id: str, provider: str) -> str | None:
    """Fetch and decrypt API key."""
    client = await get_admin_client()
    db_provider = DB_PROVIDER_MAP.get(provider, provider)
    try:
        result = await client.table("user_api_keys").select("key_encrypted").eq("user_id", user_id).eq("provider", db_provider).eq("is_active", True).execute()
        if result.data:
            return _decrypt_key(result.data[0]["key_encrypted"])
        return None
    except Exception as e:
        logger.error(f"Error fetching API key: {e}")
        return None

async def delete_api_key(user_id: str, provider: str) -> bool:
    """Delete API key for a provider."""
    client = await get_admin_client()
    db_provider = DB_PROVIDER_MAP.get(provider, provider)
    try:
        result = await client.table("user_api_keys").delete().eq("user_id", user_id).eq("provider", db_provider).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Error deleting API key: {e}")
        return False

async def get_user_providers(user_id: str) -> list[dict]:
    """Return masked API key info for user UI."""
    client = await get_admin_client()
    try:
        result = await client.table("user_api_keys").select("provider, key_preview, is_active").eq("user_id", user_id).execute()
        if result.data:
            for row in result.data:
                row["provider"] = REVERSE_PROVIDER_MAP.get(row["provider"], row["provider"])
        return result.data or []
    except Exception as e:
        logger.error(f"Error fetching user providers: {e}")
        return []
