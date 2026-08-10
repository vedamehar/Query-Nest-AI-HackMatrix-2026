from fastapi import Header, HTTPException, Depends
from typing import Annotated
from jose import jwt, JWTError
from config import settings

import logging

logger = logging.getLogger("sitesense.auth")

from .jwk_loader import verify_token

async def get_current_user(
    authorization: str = Header(None)
) -> dict:
    """
    Verifies Supabase JWT token.
    Supports both HS256 (symmetric) and ES256/RS256 (asymmetric).
    """
    if not authorization:
        logger.warning("Auth check failed: No Authorization header present")
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning(f"Auth check failed: Invalid format '{authorization[:15]}...'")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format"
        )
    
    token = authorization.replace("Bearer ", "")
    
    # Check secret if it's there
    if not settings.SUPABASE_JWT_SECRET:
        logger.error("SYSTEM ERROR: SUPABASE_JWT_SECRET is not set in config!")
        raise HTTPException(status_code=500, detail="Internal server configuration error")

    try:
        # Robust verification using JWK if needed
        payload = await verify_token(token)
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning(f"Auth check failed: Token valid but missing 'sub' claim. Payload keys: {list(payload.keys())}")
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        
        logger.info(f"Auth success: User {user_id} ({payload.get('email', 'no email')})")
        return {
            "user_id": user_id,
            "email": payload.get("email", "")
        }
    except Exception as e:
        logger.warning(f"Auth check failed: Detail: {e}. Token preview: {token[:15]}...{token[-10:]}")
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {e}. If this persists, check if your project uses ES256/RS256 JWKS."
        )

# Shorthand type for use in route parameters
CurrentUser = Annotated[dict, Depends(get_current_user)]
