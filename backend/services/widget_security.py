from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException, Request, Depends
from jose import jwt, JWTError
from config import settings

# ── LAYER 1: Domain Validation ──────────────────────────

def validate_origin(
    origin: str | None,
    allowed_origins: list[str]
) -> bool:
    """
    Returns True if origin is allowed.
    - If '*' is in allowed_origins, all origins are accepted.
    - In development (ENVIRONMENT=development), any local origin is allowed if nothing else is specified.
    - Otherwise, strictly cross-match origin against the allowed list.
    """
    # 1. Broad development bypass
    if settings.ENVIRONMENT == "development":
        # Always allow localhost, 127.0.0.1 and private network IPs in dev
        if origin and any(x in origin for x in ["localhost", "127.0.0.1", "192.168.", "10."]):
            return True
        # If no origins configured in dev, allow all
        if not allowed_origins:
            return True

    # 2. Production checks
    if not allowed_origins:
        return False # Production MUST specify origins
    
    # Wildcard support
    if "*" in allowed_origins:
        return True

    if origin is None:
        return False
    
    # 3. Strict normalized comparison
    normalized_origin = origin.rstrip("/")
    return normalized_origin in [o.rstrip("/") for o in allowed_origins]

# ── LAYER 2: Widget Session JWT ──────────────────────────

def create_widget_token(
    bot_id: str,
    domain: str
) -> str:
    """Creates short-lived JWT for widget sessions."""
    # Use timezone-aware UTC to prevent Windows host clock offset issues
    now = datetime.now(timezone.utc)
    
    # Safety: ensure duration is positive
    duration = max(1, settings.WIDGET_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "bot_id": bot_id,
        "domain": domain,
        "type": "widget_session",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=duration)).timestamp())
    }
    
    return jwt.encode(
        payload,
        settings.WIDGET_JWT_SECRET,
        algorithm="HS256"
    )

def verify_widget_token(
    token: str,
    bot_id: str
) -> dict:
    """Verifies widget JWT and checks bot_id matches."""
    import logging
    log = logging.getLogger("sitesense.auth")
    
    try:
        # Added 10s leeway to account for slight clock skews
        payload = jwt.decode(
            token,
            settings.WIDGET_JWT_SECRET,
            algorithms=["HS256"],
            options={"leeway": 10}
        )
    except JWTError as e:
        log.warning(f"Widget session token invalid/expired: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Widget session expired or invalid: {str(e)}"
        )
    
    if payload.get("type") != "widget_session":
        log.warning(f"Token type mismatch: {payload.get('type')}")
        raise HTTPException(
            status_code=401,
            detail="Invalid token type"
        )
    
    # Use lowercase comparison for bot_id to avoid case-sensitivity bugs
    if str(payload.get("bot_id")).lower() != str(bot_id).lower():
        log.warning(f"Token bot_id mismatch: {payload.get('bot_id')} vs {bot_id}")
        raise HTTPException(
            status_code=401,
            detail="Token bot_id mismatch"
        )
    
    return payload

# ── LAYER 4: Token Refresh Detection ────────────────────

def should_refresh_token(payload: dict) -> bool:
    """Returns True if token expires in less than 10 minutes."""
    exp = datetime.utcfromtimestamp(payload.get("exp", 0))
    remaining = (exp - datetime.utcnow()).total_seconds()
    return remaining < 600

# ── COMBINED DEPENDENCY ──────────────────────────────────

async def verify_widget_request(
    request: Request,
    x_bot_id: str = Header(None),
    authorization: str = Header(None)
) -> dict:
    """
    FastAPI dependency for /api/chat endpoint.
    Validates all security layers.
    Returns: {"tenant": dict, "jwt_payload": dict}
    """
    import database
    
    # Check X-Bot-Id header
    if not x_bot_id:
        raise HTTPException(
            status_code=400,
            detail="X-Bot-Id header required"
        )
    
    # Get tenant
    tenant = await database.get_tenant_by_bot_id(x_bot_id)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Bot not found"
        )
    
    # Validate origin (Layer 1)
    origin = request.headers.get("origin")
    allowed = tenant.get("allowed_origins", [])
    if not validate_origin(origin, allowed):
        raise HTTPException(
            status_code=403,
            detail="This domain is not authorized to use this bot. "
                   "Add your domain in the bot settings."
        )
    
    # Verify widget JWT (Layer 2)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Widget session token required. "
                   "Initialize the widget first."
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_widget_token(token, x_bot_id)
    
    return {"tenant": tenant, "jwt_payload": payload}
