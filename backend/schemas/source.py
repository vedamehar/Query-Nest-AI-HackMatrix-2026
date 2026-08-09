"""Source schemas — create / response / ingest request models."""

from typing import Literal

from pydantic import BaseModel


class SourceCreate(BaseModel):
    """Payload for registering a new content source."""

    tenant_id: str
    type: Literal["url", "pdf", "docx", "markdown"]
    name: str
    location: str


class SourceResponse(BaseModel):
    """Full source representation returned by the API."""
 
    id: str
    tenant_id: str
    type: str
    name: str
    location: str
    status: str
    chunk_count: int
    content_hash: str
    error_message: str
    last_indexed: str | None
    created_at: str


class IngestUrlRequest(BaseModel):
    """
    Payload for triggering URL ingestion.

    If *name* is ``None``, the router will derive
    it from the domain name of the URL.
    """

    tenant_id: str
    url: str
    name: str | None = None
