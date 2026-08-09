"""
SiteSense AI — Analytics Router

Read-only endpoints for the admin dashboard:
analytics summary, conversations, unanswered questions, leads.
Secured with admin JWT (CurrentUser).
"""

from fastapi import APIRouter, HTTPException
from middleware.auth import CurrentUser
import database

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ------------------------------------------------------------------
#  GET /api/analytics/{tenant_id} — summary dashboard
# ------------------------------------------------------------------
@router.get("/{tenant_id}")
async def get_analytics(tenant_id: str, current_user: CurrentUser):
    """
    Return an aggregated analytics snapshot for a tenant, verifying ownership.
    """
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant not found or unauthorized")

    summary = await database.get_analytics_summary(tenant_id)

    # Enrich with unanswered question texts
    unanswered = await database.get_unanswered_questions(tenant_id)
    unanswered_texts = [q["question"] for q in unanswered[:20]]

    return {
        "total_conversations": summary.get("total_conversations", 0),
        "answered_count": summary.get("answered_count", 0),
        "unanswered_count": summary.get("unanswered_count", 0),
        "answer_rate": summary.get("answer_rate", 0.0),
        "conversations_today": summary.get("conversations_today", 0),
        "total_tokens": summary.get("total_tokens", 0),
        "top_provider": summary.get("top_provider", "N/A"),
        "top_sources": summary.get("top_sources", []),
        "daily_counts": summary.get("daily_counts", []),
        "unanswered_questions": unanswered_texts,
    }


# ------------------------------------------------------------------
#  GET /api/analytics/{tenant_id}/conversations
# ------------------------------------------------------------------
@router.get("/{tenant_id}/conversations")
async def get_conversations(tenant_id: str, current_user: CurrentUser, limit: int = 50):
    """Return recent conversations for a tenant, verifying ownership."""
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant not found or unauthorized")

    conversations = await database.get_conversations_by_tenant(tenant_id, limit=limit)
    return conversations


# ------------------------------------------------------------------
#  GET /api/analytics/{tenant_id}/unanswered
# ------------------------------------------------------------------
@router.get("/{tenant_id}/unanswered")
async def get_unanswered(tenant_id: str, current_user: CurrentUser):
    """Return conversations where the bot could not answer, verifying ownership."""
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant not found or unauthorized")

    questions = await database.get_unanswered_questions(tenant_id)
    return questions


# ------------------------------------------------------------------
#  GET /api/analytics/{tenant_id}/leads
# ------------------------------------------------------------------
@router.get("/{tenant_id}/leads")
async def get_leads(tenant_id: str, current_user: CurrentUser):
    """Return captured leads for a tenant, verifying ownership."""
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant not found or unauthorized")

    leads = await database.get_leads_by_tenant(tenant_id)
    return leads
