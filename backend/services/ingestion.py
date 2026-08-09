"""
SiteSense AI — Ingestion Service

Pipeline: Extract text → Clean → Chunk → Embed → Store in ChromaDB
                                                 → Update SQLite status

Supports URL crawling (Crawl4AI), PDF extraction (PyMuPDF + OCR
fallback), and raw text/markdown ingestion.

All functions are async and designed to run as FastAPI
``BackgroundTask``s.  The calling router decides whether to
``await`` the result or dispatch it in the background.
"""

import asyncio
import hashlib
import logging
import os
import re
import httpx
from pathlib import Path

import fitz  # PyMuPDF

from crawl4ai.async_logger import AsyncLogger
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from llama_index.core.node_parser import SentenceSplitter

try:
    import pandas as pd
except ImportError:
    pd = None

from config import settings
import database
from services.chroma import (
    add_chunks_to_collection,
    delete_source_chunks,
)
from services.embeddings import get_embeddings_batch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MIN_CONTENT_LENGTH = 10  # characters

# Ensure the uploads directory exists on import
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)


# ===================================================================
#  HELPERS
# ===================================================================

def compute_hash(content: str) -> str:
    """Return the SHA-256 hex digest of *content*."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_text(text: str) -> list[str]:
    """
    Split *text* into overlapping chunks using LlamaIndex's
    ``SentenceSplitter``.

    Returns a list of non-empty text chunks.
    """
    splitter = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=50,
        paragraph_separator="\n\n",
    )
    chunks = splitter.split_text(text)
    # Filter out empty / whitespace-only chunks
    return [c for c in chunks if c.strip()]


async def check_content_changed(source_id: str, new_hash: str) -> bool:
    """
    Compare *new_hash* against the hash stored in SQLite for
    *source_id*.

    Returns ``True`` if the content has changed (or no hash
    exists yet) — meaning we should re-index.
    Returns ``False`` if the hashes match — skip re-index.
    """
    source = await database.get_source_by_id(source_id)
    if source is None:
        return True
    existing_hash = source.get("content_hash", "")
    if not existing_hash:
        return True
    return existing_hash != new_hash


def _build_chunk_metadata(
    *,
    tenant_id: str,
    bot_id: str,
    source_id: str,
    source_name: str,
    source_url: str,
    chunk_index: int,
    source_type: str,
    content_hash: str,
) -> dict:
    """Build the standard per-chunk metadata dict."""
    return {
        "tenant_id": tenant_id,
        "bot_id": bot_id,
        "source_id": source_id,
        "source_name": source_name,
        "source_url": source_url,
        "chunk_index": chunk_index,
        "type": source_type,
        "content_hash": content_hash,
    }


def _build_chunk_id(source_id: str, index: int) -> str:
    """Return the deterministic chunk ID ``{source_id}_chunk_{index}``."""
    return f"{source_id}_chunk_{index}"


# ===================================================================
#  CORE INGESTION PIPELINE (shared tail)
# ===================================================================

async def _run_pipeline(
    *,
    tenant_id: str,
    bot_id: str,
    source_id: str,
    source_name: str,
    source_url: str,
    source_type: str,
    content: str,
) -> dict:
    """
    Shared pipeline tail used by all ingest_* functions after
    raw text has been extracted.

    Steps: hash → delete old chunks → chunk → embed → store → update DB.
    """
    # --- Validate minimum content length ---
    if len(content.strip()) < MIN_CONTENT_LENGTH:
        raise ValueError(
            f"Extracted content too short ({len(content.strip())} chars). "
            f"Minimum is {MIN_CONTENT_LENGTH} characters."
        )

    # --- Hash ---
    content_hash = compute_hash(content)

    # --- Delete previous chunks for this source (re-index) ---
    await delete_source_chunks(bot_id, source_id)

    # --- Chunk ---
    chunks = chunk_text(content)
    if not chunks:
        raise ValueError("Text chunking produced zero chunks.")

    # --- Embed ---
    embeddings = await get_embeddings_batch(chunks, input_type="document")

    # --- Build metadata & IDs ---
    metadatas = [
        _build_chunk_metadata(
            tenant_id=tenant_id,
            bot_id=bot_id,
            source_id=source_id,
            source_name=source_name,
            source_url=source_url,
            chunk_index=i,
            source_type=source_type,
            content_hash=content_hash,
        )
        for i in range(len(chunks))
    ]
    ids = [_build_chunk_id(source_id, i) for i in range(len(chunks))]

    # --- Store in ChromaDB ---
    added = await add_chunks_to_collection(
        bot_id=bot_id,
        chunks=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )

    # --- Update source record in SQLite ---
    await database.update_source_status(
        source_id=source_id,
        status="indexed",
        chunk_count=added,
        content_hash=content_hash,
        error_message="",  # Clear previous errors
    )

    logger.info(
        "Ingestion complete for source %s (%s) — %d chunks indexed",
        source_id,
        source_type,
        added,
    )
    return {"status": "indexed", "chunks": added}


async def _fail_source(source_id: str, error: Exception) -> dict:
    """Mark the source as failed in SQLite and return error dict."""
    error_msg = str(error)
    logger.error("Ingestion failed for source %s: %s", source_id, error_msg)
    await database.update_source_status(
        source_id=source_id,
        status="failed",
        error_message=error_msg,
    )
    return {"status": "failed", "error": error_msg}


# ===================================================================
#  URL INGESTION
# ===================================================================

async def ingest_url(
    tenant_id: str,
    bot_id: str,
    source_id: str,
    source_name: str,
    url: str,
) -> bool:
    """Scrape and index a URL with Windows-safe fallbacks."""
    try:
        await database.update_source_status(source_id=source_id, status="indexing")
        logger.info(f"Starting ingestion for URL: {url}")

        content = ""
        # Tier 1: Try Crawl4AI (Browser mode)
        try:
            config = CrawlerRunConfig(
                cache_mode="bypass",
                excluded_tags=["nav", "footer", "script", "style"],
            )
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)
                
            if result and (result.markdown or result.markdown_v2):
                content = result.markdown or result.markdown_v2.raw_markdown
                logger.info("Content extracted via Crawl4AI browser")
        except Exception as e:
            logger.warning(f"Crawl4AI failed (Windows browser error?), using fallback: {str(e)}")

        # Tier 2: Fallback to HTTPX (Static mode)
        if not content:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                # Remove Boilerplate (scripts, styles, nav, footer)
                html = re.sub(r'<(script|style|nav|footer|header).*?>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<[^>]+>', ' ', html)
                content = re.sub(r'\s+', ' ', content).strip()
                logger.info("Content extracted via HTTPX fallback")

        if not content:
            raise ValueError(f"Failed to extract any content from {url}")

        # 3. Run shared pipeline
        return await _run_pipeline(
            tenant_id=tenant_id,
            bot_id=bot_id,
            source_id=source_id,
            source_name=source_name,
            source_url=url,
            source_type="url",
            content=content,
        )

    except Exception as exc:
        logger.error(f"URL Ingestion failed: {str(exc)}")
        await database.update_source_status(
            source_id=source_id, 
            status="error", 
            error_message=str(exc)
        )
        return False


# ===================================================================
#  PDF INGESTION
# ===================================================================

def _extract_pdf_text(file_path: str) -> str:
    """
    Extract text from a PDF using PyMuPDF (synchronous).

    Falls back to OCR via pytesseract if the text layer
    is empty or too short.
    """
    doc = fitz.open(file_path)
    pages: list[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text").strip()
        if page_text:
            pages.append(f"[Page {page_num + 1}]\n{page_text}")

    doc.close()
    full_text = "\n\n".join(pages)

    # -- OCR fallback if text is empty / too short --
    if len(full_text.strip()) < MIN_CONTENT_LENGTH:
        full_text = _ocr_pdf(file_path)

    return full_text


def _ocr_pdf(file_path: str) -> str:
    """
    Render each page of a PDF as an image and OCR with
    pytesseract (synchronous fallback).
    """
    try:
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(file_path)
        pages: list[str] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render at 2x for better OCR accuracy
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(img).strip()
            if page_text:
                pages.append(f"[Page {page_num + 1}]\n{page_text}")

        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        logger.warning(
            "pytesseract or Pillow not available — OCR fallback skipped"
        )
        return ""
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def _extract_text_from_file(file_path: str) -> str:
    """
    Extract text content from various file types.
    Supported: .pdf, .txt, .md, .xlsx, .xls
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        return _extract_pdf_text(file_path)
    
    elif ext in [".txt", ".md", ".csv"]:
        try:
            if ext == ".csv":
                if pd is None:
                    return "[Error: pandas not installed on server]"
                # Use robust settings for CSV parsing to handle mismatched columns
                df = pd.read_csv(
                    file_path, 
                    on_bad_lines='skip', 
                    encoding_errors='replace'
                )
                return df.to_string(index=False)
            
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Text/CSV extraction failed: {str(e)}")
            return f"[Error: {str(e)}]"
            
    elif ext in [".xlsx", ".xls"]:
        if pd is None:
            return "[Error: pandas/openpyxl not installed on server]"
            
        try:
            # Read all sheets
            excel_data = pd.read_excel(file_path, sheet_name=None)
            full_text_list = []
            for sheet_name, df in excel_data.items():
                if df.empty:
                    continue
                # Convert sheet to CSV-like text for best RAG performance
                sheet_text = f"--- Sheet: {sheet_name} ---\n"
                sheet_text += df.to_string(index=False)
                full_text_list.append(sheet_text)
            return "\n\n".join(full_text_list)
        except Exception as e:
            logger.error(f"Excel extraction failed: {str(e)}")
            return f"[Error extracting Excel: {str(e)}]"
            
    else:
        # Generic fallback
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except:
            return ""


async def ingest_file(
    tenant_id: str,
    bot_id: str,
    source_id: str,
    file_path: str,
    filename: str,
) -> bool:
    """
    Generic file ingestion (PDF, TXT, MD, CSV, Excel).
    """
    try:
        # 1. Mark indexing
        await database.update_source_status(source_id=source_id, status="indexing")

        # 2. Validate file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File exceeds limit ({file_size / 1024 / 1024:.1f} MB)"
            )

        # 3. Detect type and extract
        ext = os.path.splitext(filename)[1].lower()
        source_type = ext.replace(".", "") or "file"
        
        # Ensure we categorize .xlsx/.xls as 'excel'
        if ext in [".xlsx", ".xls"]:
            source_type = "excel"
        elif ext == ".csv":
            source_type = "csv"

        content = await asyncio.to_thread(_extract_text_from_file, file_path)

        if not content or not content.strip():
            raise ValueError(f"No text could be extracted from file: {filename}")

        # 4. Run shared pipeline
        return await _run_pipeline(
            tenant_id=tenant_id,
            bot_id=bot_id,
            source_id=source_id,
            source_name=filename,
            source_url=filename,
            source_type=source_type,
            content=content,
        )

    except Exception as exc:
        logger.error(f"File Ingestion failed ({filename}): {str(exc)}")
        await database.update_source_status(
            source_id=source_id, 
            status="error", 
            error_message=str(exc)
        )
        return False


# ===================================================================
#  TEXT / MARKDOWN INGESTION
# ===================================================================

async def ingest_text(
    tenant_id: str,
    bot_id: str,
    source_id: str,
    text_content: str,
    source_name: str,
) -> dict:
    """
    Ingest raw text or markdown content (no extraction step).
    """
    try:
        # 1. Mark indexing
        await database.update_source_status(source_id=source_id, status="indexing")

        if not text_content or not text_content.strip():
            raise ValueError("Provided text content is empty.")

        # 2. Run shared pipeline
        return await _run_pipeline(
            tenant_id=tenant_id,
            bot_id=bot_id,
            source_id=source_id,
            source_name=source_name,
            source_url=source_name,
            source_type="markdown",
            content=text_content,
        )

    except Exception as exc:
        logger.error(f"Text Ingestion failed: {str(exc)}")
        await database.update_source_status(
            source_id=source_id, 
            status="error", 
            error_message=str(exc)
        )
        return False
