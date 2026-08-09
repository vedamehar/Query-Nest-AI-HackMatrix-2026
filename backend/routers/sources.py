"""
SiteSense AI — Sources Router

Manages content sources (URLs, PDFs) and triggers
ingestion as background tasks.
Secured with admin JWT (CurrentUser).
"""

import os
import uuid
from urllib.parse import urlparse

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile, File
from typing import List

import database
from config import settings
from schemas.source import IngestUrlRequest, SourceResponse
from services.chroma import delete_source_chunks
from services.ingestion import ingest_file, ingest_text, ingest_url
from middleware.auth import CurrentUser

router = APIRouter(prefix="/api/sources", tags=["sources"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ------------------------------------------------------------------
#  GET /api/sources/{tenant_id} — list sources for a tenant
# ------------------------------------------------------------------
@router.get("/{tenant_id}", response_model=List[SourceResponse])
async def list_sources(tenant_id: str, current_user: CurrentUser):
    """Return all content sources for a tenant, verifying ownership."""
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant not found or unauthorized")

    sources = await database.get_sources_by_tenant(tenant_id)
    return sources


# ------------------------------------------------------------------
#  POST /api/sources/ingest/url — ingest from URL
# ------------------------------------------------------------------
@router.post("/ingest/url", response_model=SourceResponse, status_code=202)
async def ingest_url_endpoint(
    body: IngestUrlRequest, 
    background_tasks: BackgroundTasks,
    current_user: CurrentUser
):
    """
    Start URL ingestion as a background task.
    Returns the source record immediately with ``status=pending``.
    """
    # 1. Validate tenant ownership
    tenant = await database.get_tenant_by_id(body.tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant not found or unauthorized")

    # 2. Derive name from domain if not provided
    name = body.name
    if not name:
        parsed = urlparse(body.url)
        name = parsed.netloc or body.url

    # 3. Create source record (status=pending)
    source = await database.create_source(
        tenant_id=body.tenant_id,
        type="url",
        name=name,
        location=body.url,
    )

    # 4. Dispatch background ingestion
    background_tasks.add_task(
        ingest_url,
        tenant_id=body.tenant_id,
        bot_id=tenant["bot_id"],
        source_id=source["id"],
        url=body.url,
        source_name=name,
    )

    return source


# ------------------------------------------------------------------
#  POST /api/sources/ingest/file — ingest uploaded file (PDF, TXT, MD, Excel)
# ------------------------------------------------------------------
@router.post("/ingest/file", response_model=SourceResponse, status_code=202)
async def ingest_file_endpoint(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
    name: str = Form(None),
):
    """
    Upload a file and start ingestion as a background task.
    Supports .pdf, .txt, .md, .xlsx, .xls
    """
    # 1. Validate tenant ownership
    tenant = await database.get_tenant_by_id(tenant_id, current_user["user_id"])
    if tenant is None:
        raise HTTPException(status_code=403, detail="Tenant not found or unauthorized")

    # 2. Validate file type
    ALLOWED_TYPES = (
        "application/pdf",
        "application/x-pdf",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
        "application/vnd.ms-excel",  # .xls
    )
    if file.content_type not in ALLOWED_TYPES:
        # Fallback check for extension if content_type is generic
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in (".pdf", ".txt", ".md", ".xlsx", ".xls", ".csv"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.content_type}. Supported: PDF, TXT, MD, CSV, Excel.",
            )

    # 3. Validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds 50 MB limit ({len(contents) / 1024 / 1024:.1f} MB).",
        )

    # 4. Save to uploads directory
    original_filename = name or file.filename or "document"
    ext = os.path.splitext(file.filename or "doc")[1]
    unique_name = f"{tenant_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(settings.UPLOADS_DIR, unique_name)

    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    # 5. Create source record
    # Deduce type for the record
    source_type = ext.replace(".", "").lower() if ext else "file"
    if source_type in ("xlsx", "xls"):
        source_type = "excel"

    source = await database.create_source(
        tenant_id=tenant_id,
        type=source_type,
        name=original_filename,
        location=file_path,
    )

    # 6. Dispatch background ingestion
    background_tasks.add_task(
        ingest_file,
        tenant_id=tenant_id,
        bot_id=tenant["bot_id"],
        source_id=source["id"],
        file_path=file_path,
        filename=original_filename,
    )

    return source


# Backwards compatibility wrapper for /ingest/pdf
@router.post("/ingest/pdf", include_in_schema=False)
async def legacy_ingest_pdf(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
    name: str = Form(None),
):
    return await ingest_file_endpoint(background_tasks, current_user, file, tenant_id, name)


# ------------------------------------------------------------------
#  GET /api/sources/status/{source_id} — poll source status
# ------------------------------------------------------------------
@router.get("/status/{source_id}")
async def get_source_status(source_id: str, current_user: CurrentUser):
    """Return the current indexing status of a source."""
    source = await database.get_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Verify ownership of the parent tenant
    tenant = await database.get_tenant_by_id(source["tenant_id"], current_user["user_id"])
    if not tenant:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return {
        "id": source["id"],
        "status": source["status"],
        "chunk_count": source["chunk_count"],
        "error_message": source["error_message"],
    }


# ------------------------------------------------------------------
#  DELETE /api/sources/{source_id} — delete source
# ------------------------------------------------------------------
@router.delete("/{source_id}")
async def delete_source(source_id: str, current_user: CurrentUser):
    """
    Delete a source:
    1. Remove chunks from ChromaDB
    2. Remove record from database
    3. Remove uploaded file (if PDF)
    """
    source = await database.get_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Verify ownership of the parent tenant
    tenant = await database.get_tenant_by_id(source["tenant_id"], current_user["user_id"])
    if not tenant:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # 1. Remove chunks from ChromaDB
    try:
        await delete_source_chunks(tenant["bot_id"], source_id)
    except Exception:
        pass  # Best-effort

    # 2. Delete uploaded file if it's a PDF
    if source["type"] == "pdf" and source.get("location"):
        try:
            if os.path.exists(source["location"]):
                os.remove(source["location"])
        except OSError:
            pass

    # 3. Delete from database
    await database.delete_source(source_id)
    return {"success": True}


# ------------------------------------------------------------------
#  POST /api/sources/reindex/{source_id} — re-ingest source
# ------------------------------------------------------------------
@router.post("/reindex/{source_id}", response_model=SourceResponse, status_code=202)
async def reindex_source(
    source_id: str, 
    background_tasks: BackgroundTasks,
    current_user: CurrentUser
):
    """
    Trigger re-ingestion of an existing source.
    Resets status to ``pending`` and dispatches background task.
    """
    source = await database.get_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Verify ownership of the parent tenant
    tenant = await database.get_tenant_by_id(source["tenant_id"], current_user["user_id"])
    if not tenant:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Reset status
    await database.update_source_status(
        source_id=source_id,
        status="pending",
        error_message="",  # Clear old error for the new attempt
    )

    # Dispatch based on source type
    if source["type"] == "url":
        background_tasks.add_task(
            ingest_url,
            tenant_id=source["tenant_id"],
            bot_id=tenant["bot_id"],
            source_id=source_id,
            url=source["location"],
            source_name=source["name"],
        )
    elif source["type"] in ("pdf", "txt", "md", "markdown", "docx", "text", "excel", "xlsx", "xls", "csv"):
        if os.path.exists(source["location"]):
            background_tasks.add_task(
                ingest_file,
                tenant_id=source["tenant_id"],
                bot_id=tenant["bot_id"],
                source_id=source_id,
                file_path=source["location"],
                filename=source["name"],
            )
        else:
            await database.update_source_status(
                source_id=source_id,
                status="failed",
                error_message=f"Source file not found: {source['location']}",
            )

    # Re-fetch and return updated source
    updated = await database.get_source_by_id(source_id)
    return updated
