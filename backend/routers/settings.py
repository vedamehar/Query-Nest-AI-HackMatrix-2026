from fastapi import APIRouter, HTTPException
from middleware.auth import CurrentUser
from database import (
    save_api_key, get_user_providers, 
    delete_api_key, get_api_key
)
from pydantic import BaseModel
from services.llm_provider import get_available_models

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SaveApiKeyRequest(BaseModel):
    provider: str
    api_key: str

@router.get("/providers")
async def get_providers(current_user: CurrentUser):
    """Get user's configured API providers (preview only)"""
    providers = await get_user_providers(current_user["user_id"])
    return {"providers": providers}

@router.post("/api-key")
async def save_key(
    body: SaveApiKeyRequest,
    current_user: CurrentUser
):
    """Save encrypted API key for a provider"""
    valid_providers = [
        "anthropic", "gemini", 
        "voyage", "openrouter", "claude"
    ]
    if body.provider not in valid_providers:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    api_key = body.api_key.strip()
    if len(api_key) < 10:
        raise HTTPException(status_code=400, detail="Invalid API key")
    
    result = await save_api_key(
        current_user["user_id"],
        body.provider,
        api_key
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to save API key")
        
    return {
        "success": True, 
        "provider": body.provider,
        "preview": result.get("key_preview")
    }

@router.delete("/api-key/{provider}")
async def delete_key(
    provider: str,
    current_user: CurrentUser
):
    """Delete saved API key"""
    await delete_api_key(current_user["user_id"], provider)
    return {"success": True}

@router.get("/models")
async def get_models(current_user: CurrentUser):
    """Get available models per provider"""
    return get_available_models()
