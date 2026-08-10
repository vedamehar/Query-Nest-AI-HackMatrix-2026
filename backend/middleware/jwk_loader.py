
import httpx
import logging
from jose import jwk, jwt
from jose.exceptions import JWTError
from config import settings

logger = logging.getLogger("sitesense.jwk")

_jwks_cache = None

async def get_jwks():
    """Fetches and caches the JWKS from Supabase project."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    try:
        url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            res.raise_for_status()
            _jwks_cache = res.json()
            return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to fetch JWKS from Supabase: {e}")
        return None

async def verify_token(token: str) -> dict:
    """
    Robust JWT verification.
    1. If HS256, uses SUPABASE_JWT_SECRET.
    2. If ES256/RS256, uses project JWKS.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        
        if alg == "HS256":
            # Symmetric verification using secret string
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
        
        # Asymmetric verification using JWKS
        jwks = await get_jwks()
        if not jwks:
            raise JWTError("JWKS not available")
            
        return jwt.decode(
            token,
            jwks,
            algorithms=[alg],
            options={"verify_aud": False}
        )
    except JWTError as e:
        logger.warning(f"JWT verification failed ({alg}): {e}")
        raise
