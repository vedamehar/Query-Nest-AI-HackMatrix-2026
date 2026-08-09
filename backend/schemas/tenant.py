"""Tenant schemas — create / update / response models."""

from pydantic import BaseModel


class TenantCreate(BaseModel):
    """Payload for creating a new tenant."""

    name: str
    bot_name: str = "AI Assistant"
    welcome_message: str = "Hi! How can I help you?"
    fallback_message: str = "I don't have information on that topic."
    primary_color: str = "#2563eb"
    system_prompt: str = ""
    allowed_origins: list[str] = []
    llm_provider: str = "claude"
    llm_model: str = "claude-haiku-4-5-20251001"
    suggested_questions: list[str] = []


class TenantUpdate(BaseModel):
    """Payload for partially updating a tenant (all fields optional)."""

    name: str | None = None
    bot_name: str | None = None
    welcome_message: str | None = None
    fallback_message: str | None = None
    primary_color: str | None = None
    system_prompt: str | None = None
    allowed_origins: list[str] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    suggested_questions: list[str] | None = None


class TenantResponse(BaseModel):
    """Full tenant representation returned by the API."""

    id: str
    name: str
    bot_id: str
    bot_name: str
    welcome_message: str
    fallback_message: str
    primary_color: str
    system_prompt: str
    allowed_origins: list[str]
    llm_provider: str
    llm_model: str
    suggested_questions: list[str]
    created_at: str
