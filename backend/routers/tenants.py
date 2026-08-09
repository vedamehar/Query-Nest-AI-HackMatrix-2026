"""
SiteSense AI — Tenants Router

CRUD operations for tenants (chatbot instances).
Secured with admin JWT (CurrentUser).
"""

from fastapi import APIRouter, HTTPException
from typing import List

import database
from schemas.tenant import TenantCreate, TenantResponse, TenantUpdate
from services.chroma import delete_tenant_collection, get_or_create_collection
from middleware.auth import CurrentUser

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


# ------------------------------------------------------------------
#  GET /api/tenants — list all tenants for current user
# ------------------------------------------------------------------
@router.get("", response_model=List[TenantResponse])
async def list_tenants(current_user: CurrentUser):
    """Return every tenant owned by the current user, newest first."""
    tenants = await database.get_all_tenants(user_id=current_user["user_id"])
    return tenants


# ------------------------------------------------------------------
#  POST /api/tenants — create a new tenant
# ------------------------------------------------------------------
@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(body: TenantCreate, current_user: CurrentUser):
    """Create a new tenant and its ChromaDB collection."""
    tenant = await database.create_tenant(
        user_id=current_user["user_id"],
        name=body.name,
        bot_name=body.bot_name,
        welcome_message=body.welcome_message,
        fallback_message=body.fallback_message,
        primary_color=body.primary_color,
        system_prompt=body.system_prompt,
        allowed_origins=body.allowed_origins,
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
        suggested_questions=body.suggested_questions,
    )

    if not tenant:
        raise HTTPException(status_code=500, detail="Failed to create tenant")

    # Create the ChromaDB collection eagerly
    try:
        await get_or_create_collection(tenant["bot_id"])
    except Exception:
        pass  # Non-fatal — collection will be created on first ingest

    return tenant


# ------------------------------------------------------------------
#  GET /api/tenants/{tenant_id} — get single tenant
# ------------------------------------------------------------------
@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str, current_user: CurrentUser):
    """Return a single tenant by ID, verifying ownership."""
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found or unauthorized")
    return tenant


# ------------------------------------------------------------------
#  PUT /api/tenants/{tenant_id} — update tenant
# ------------------------------------------------------------------
@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(tenant_id: str, body: TenantUpdate, current_user: CurrentUser):
    """Update tenant fields (only supplied fields are changed), verifying ownership."""
    # Ownership is verified inside the DB function (passing user_id)
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        # Just return existing if no updates
        res = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
        if not res:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return res

    updated = await database.update_tenant(tenant_id, current_user["user_id"], update_data)
    if updated is None or not updated:
        raise HTTPException(status_code=404, detail="Tenant not found or unauthorized")
    return updated


# ------------------------------------------------------------------
#  DELETE /api/tenants/{tenant_id} — delete tenant
# ------------------------------------------------------------------
@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, current_user: CurrentUser):
    """
    Delete a tenant, its ChromaDB collection, and all
    related sources / conversations / leads.
    """
    # 1. Fetch tenant to get bot_id (for chroma) and verify ownership
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found or unauthorized")

    # 2. Delete ChromaDB collection
    try:
        await delete_tenant_collection(tenant["bot_id"])
    except Exception:
        pass  # Best-effort

    # 3. Delete from database (cascade handles sources/conversations)
    success = await database.delete_tenant(tenant_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete tenant")
        
    return {"success": True}
