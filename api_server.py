"""
FastAPI application: Exposes the guarded retrieval pipeline.
Single endpoint POST /ask - no direct model access.
"""
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List
from pathlib import Path
import os
import time
from datetime import datetime
import shutil
import uuid
import asyncio
import threading
import traceback

# ✅ CRITICAL: Import config module
import config

# ✅ COMPLIANCE SYSTEM: Import compliance response formatter
from compliance_response_integration import enforce_compliance_on_response

# ✅ VIDEO TRANSCRIPTION: Import video integration
from video_integration import get_video_handler, load_whisper_model
from graph_service import KnowledgeGraphService

# Global progress tracker for uploads
upload_progress = {}
# Track active upload tasks for cancellation
active_uploads = {}
# Track existing documents (name + version combinations)
existing_documents = {}

# Video handler (singleton)
video_handler = None
graph_service = None
graph_rebuild_progress = {}


class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = "default_user"
    session_id: Optional[str] = None  # ✅ NEW: Session-based memory
    context: Optional[str] = None
    video_id: Optional[str] = None  # NEW: Video-specific query support


class QueryResponse(BaseModel):
    success: bool = False
    message: str = ""
    compliance_allowed: bool = False
    response_valid: Optional[bool] = False
    retrieved_documents: List[dict] = Field(default_factory=list)
    validation_issues: List[str] = Field(default_factory=list)
    audit_log_id: int = 0
    timestamp: str = ""
    answer: Optional[str] = None
    answer_citations: List[dict] = Field(default_factory=list)
    compliance_status: str = "approved"
    processing_details: dict = Field(default_factory=dict)
    session_id: Optional[str] = None  # ✅ NEW: Session tracking


def load_existing_documents():
    """Load all previously uploaded documents from the uploads folder."""
    global existing_documents
    upload_dir = Path("uploads")
    if not upload_dir.exists():
        existing_documents = {}
        return
    
    existing_documents = {}
    # Parse filenames: {document_name}_{version}_{upload_id}.{ext}
    for file_path in upload_dir.glob("*"):
        if file_path.is_file() and file_path.name != "temp":
            parts = file_path.stem.split("_")
            if len(parts) >= 2:
                # Reconstruct document name and version
                # Format: {name}_{version}_{id}
                version_part = None
                name_parts = []
                for part in parts[:-1]:  # Exclude upload_id
                    if part.startswith("v") and any(c.isdigit() for c in part):
                        version_part = part
                        break
                    name_parts.append(part)
                
                if version_part and name_parts:
                    doc_name = "_".join(name_parts)
                    doc_key = f"{doc_name}||{version_part}"
                    if doc_key not in existing_documents:
                        existing_documents[doc_key] = str(file_path)
    
    print(f"[INIT] Loaded {len(existing_documents)} existing documents")


def create_app(pipeline):
    """Factory to create FastAPI app with pipeline."""
    app = FastAPI(
        title="SocialLink Offline AI Assistant",
        description="Compliance-driven, document-grounded knowledge system",
        version="1.0.0"
    )
    
    cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
    allow_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]
    if not allow_origins:
        allow_origins = ["*"]
    allow_credentials = "*" not in allow_origins

    # Add CORS middleware to allow cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ============================================================
    # ADMIN ENDPOINTS (NEW)
    # ============================================================
    
    @app.get("/admin/documents")
    async def get_documents_list():
        """Get list of uploaded documents."""
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return []
        
        documents = []
        for file_path in upload_dir.glob("*"):
            if file_path.is_file() and file_path.name != "temp":
                stat = file_path.stat()
                documents.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "uploadedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "version": "1.0"
                })
        return documents
    
    @app.delete("/admin/documents/{doc_name}")
    async def delete_document_endpoint(doc_name: str):
        """Delete a document."""
        try:
            file_path = Path("uploads") / doc_name
            if file_path.exists():
                file_path.unlink()
                return {"success": True, "message": f"Document {doc_name} deleted"}
            else:
                raise HTTPException(status_code=404, detail="Document not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/rebuild-index")
    async def rebuild_index_endpoint():
        """Rebuild the FAISS index."""
        try:
            from initialize_kb import reinitialize_index
            reinitialize_index()
            return {"success": True, "message": "Index rebuilt successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/admin/system-status")
    async def get_system_status():
        """Get system status and statistics."""
        try:
            from pathlib import Path
            import os
            
            upload_dir = Path("uploads")
            doc_count = len(list(upload_dir.glob("*"))) if upload_dir.exists() else 0
            
            faiss_file = Path(config.FAISS_INDEX_FILE)
            index_size = f"{faiss_file.stat().st_size / 1024 / 1024:.2f}MB" if faiss_file.exists() else "0MB"
            
            return {
                "status": "online",
                "uptime": "running",
                "documents_indexed": doc_count,
                "vector_index_size": index_size,
                "model_info": f"{config.LLM_MODEL} (Ollama)",
                "last_update": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "documents_indexed": 0,
                "vector_index_size": "0MB",
                "model_info": "unknown",
                "last_update": datetime.now().isoformat()
            }
    
    @app.get("/admin/audit-logs")
    async def get_audit_logs(limit: int = 50):
        """Get recent audit logs."""
        try:
            from audit_logger import get_recent_logs
            return get_recent_logs(limit)
        except Exception:
            return []

    # ============================================================
    # KNOWLEDGE GRAPH ENDPOINTS (ISOLATED FEATURE)
    # ============================================================

    def get_graph_service() -> KnowledgeGraphService:
        global graph_service
        if graph_service is None:
            graph_service = KnowledgeGraphService(
                db_path=config.GRAPH_DB_PATH,
                llm_controller=pipeline.llm_controller,
            )
        return graph_service

    def _extract_chunk_text(meta: dict) -> str:
        return (
            str(meta.get("text") or "")
            or str(meta.get("content") or "")
            or str(meta.get("metadata", {}).get("text") or "")
        )

    def _build_graph_chunks(include_video: bool, max_chunks: Optional[int]) -> List[dict]:
        metadata = getattr(pipeline.retriever.vector_store, "metadata", []) or []
        chunks: List[dict] = []
        for idx, meta in enumerate(metadata):
            if not include_video and (meta.get("video_id") or meta.get("metadata", {}).get("video_id")):
                continue
            text = _extract_chunk_text(meta).strip()
            if not text:
                continue
            source_id = str(meta.get("chunk_id") or meta.get("source") or f"meta_{idx}")
            chunks.append({"source_id": source_id, "text": text[: config.GRAPH_MAX_SOURCE_CHARS]})

        if max_chunks and max_chunks > 0:
            return chunks[:max_chunks]

        default_limit = getattr(config, "GRAPH_REBUILD_CHUNK_LIMIT", 0)
        if default_limit and default_limit > 0:
            return chunks[:default_limit]
        return chunks

    def _rebuild_graph_background(bot_id: str, include_video: bool, max_chunks: Optional[int]) -> None:
        started_at = datetime.utcnow().isoformat()
        graph_rebuild_progress[bot_id] = {
            "status": "processing",
            "started_at": started_at,
            "updated_at": started_at,
            "chunks_processed": 0,
            "total_chunks": 0,
            "triplets_written": 0,
            "errors": 0,
        }
        try:
            chunks = _build_graph_chunks(include_video=include_video, max_chunks=max_chunks)
            graph_rebuild_progress[bot_id]["total_chunks"] = len(chunks)

            def _on_progress(processed: int, total: int, triplets: int, errs: int) -> None:
                graph_rebuild_progress[bot_id].update(
                    {
                        "status": "processing",
                        "updated_at": datetime.utcnow().isoformat(),
                        "chunks_processed": processed,
                        "total_chunks": total,
                        "triplets_written": triplets,
                        "errors": errs,
                    }
                )

            if not chunks:
                graph_rebuild_progress[bot_id] = {
                    "status": "completed",
                    "started_at": started_at,
                    "updated_at": datetime.utcnow().isoformat(),
                    "finished_at": datetime.utcnow().isoformat(),
                    "chunks_processed": 0,
                    "total_chunks": 0,
                    "triplets_written": 0,
                    "errors": 0,
                }
                return

            result = get_graph_service().rebuild_from_chunks(
                bot_id=bot_id,
                chunks=chunks,
                clear_existing=True,
                progress_callback=_on_progress,
            )
            graph_rebuild_progress[bot_id] = {
                "status": "completed",
                "started_at": started_at,
                "updated_at": datetime.utcnow().isoformat(),
                "finished_at": datetime.utcnow().isoformat(),
                "chunks_processed": result.chunks_processed,
                "total_chunks": len(chunks),
                "triplets_written": result.triplets_written,
                "errors": result.errors,
            }
        except Exception as e:
            graph_rebuild_progress[bot_id] = {
                "status": "error",
                "started_at": started_at,
                "updated_at": datetime.utcnow().isoformat(),
                "finished_at": datetime.utcnow().isoformat(),
                "error": str(e),
            }

    @app.get("/graph/{bot_id}")
    async def get_graph(bot_id: str):
        """Return graph payload: nodes + edges."""
        try:
            payload = get_graph_service().get_graph_data(bot_id)
            return {"status": "success", "bot_id": bot_id, **payload}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/graph/{bot_id}/status")
    async def get_graph_rebuild_status(bot_id: str):
        """Return async rebuild status for a bot graph."""
        return graph_rebuild_progress.get(bot_id, {"status": "idle"})

    @app.post("/graph/{bot_id}/rebuild", status_code=202)
    async def rebuild_graph(
        bot_id: str,
        background_tasks: BackgroundTasks,
        include_video: bool = False,
        max_chunks: Optional[int] = None,
    ):
        """
        Trigger async graph rebuild from indexed chunk metadata.
        Returns immediately to avoid long-request timeouts.
        """
        if graph_rebuild_progress.get(bot_id, {}).get("status") == "processing":
            return {"status": "accepted", "message": "Graph rebuild already in progress", "bot_id": bot_id}

        background_tasks.add_task(_rebuild_graph_background, bot_id, include_video, max_chunks)
        return {
            "status": "accepted",
            "message": "Graph rebuild queued",
            "bot_id": bot_id,
            "include_video": include_video,
            "max_chunks": max_chunks,
        }
    
    @app.post("/upload-document")
    async def upload_document_endpoint(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
        """
        Upload a new document and trigger embedding pipeline.
        ✅ FIXED: Now properly triggers document ingestion, chunking, embedding, and FAISS indexing
        """
        try:
            print(f"\n[UPLOAD] Document upload started: {file.filename}")
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            
            # Generate upload ID for tracking
            upload_id = str(uuid.uuid4())[:8]
            
            # Extract document name and version from filename
            # Format: document_v1.pdf → name=document, version=v1
            stem = Path(file.filename).stem
            file_ext = Path(file.filename).suffix
            
            # Try to parse version from filename
            parts = stem.rsplit('_', 1)
            if len(parts) == 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
                document_name = parts[0]
                version = parts[1]
            else:
                document_name = stem
                version = "v1"
            
            document_type = "document"  # Default type
            
            # Save the file
            saved_filename = f"{document_name}_{version}_{upload_id}{file_ext}"
            file_path = upload_dir / saved_filename
            
            print(f"[UPLOAD] Saving: {file_path}")
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            print(f"[UPLOAD] ✓ File saved: {file_path}")
            
            # Track active upload for potential cancellation
            active_uploads[upload_id] = {"file_path": str(file_path), "cancelled": False}
            
            # ✅ CRITICAL: Register in existing_documents to prevent duplicates
            doc_key = f"{document_name}||{version}"
            existing_documents[doc_key] = str(file_path)
            
            # ✅ CRITICAL: Trigger background ingestion task
            print(f"[UPLOAD] ✓ Queuing ingestion pipeline...")
            background_tasks.add_task(
                process_document_background, 
                str(file_path), 
                document_name, 
                document_type, 
                version, 
                upload_id
            )
            
            return {
                "id": upload_id,
                "status": "accepted",
                "message": f"Document '{document_name}' queued for processing",
                "upload_id": upload_id,
                "file_path": str(file_path),
                "document_name": document_name,
                "version": version
            }
        except Exception as e:
            print(f"[UPLOAD] ✗ Upload failed: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/upload-status/{upload_id}")
    async def get_upload_status_endpoint(upload_id: str):
        """Get upload status."""
        status = upload_progress.get(upload_id, {"status": "unknown"})
        return status
    
    # ============================================================
    # VIDEO TRANSCRIPTION ENDPOINTS (NEW)
    # ============================================================
    
    @app.post("/video/upload")
    async def upload_video(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
        """
        Upload video for transcription.
        
        Flow:
        - Accept MP4 file
        - Generate video_id (UUID)
        - Auto-transcribe with Whisper
        - Chunk and prepare for embedding
        - Embed chunks and add to FAISS
        - Return video_id
        """
        try:
            global video_handler
            if video_handler is None:
                video_handler = get_video_handler()
            
            # Save temp file
            temp_dir = Path("uploads/video_temp")
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{uuid.uuid4()}.mp4"
            
            with open(temp_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            # Transcribe & process
            video_id, metadata, transcript = video_handler.upload_and_transcribe(
                str(temp_path), file.filename
            )
            
            # Chunk transcript
            chunks = video_handler.chunk_transcript(transcript, video_id, file.filename)
            
            # ✅ NEW: Embed and add chunks to FAISS vector store
            try:
                print(f"[VIDEO] Embedding {len(chunks)} chunks into vector store...")
                from vector_store import VectorStore, EmbeddingModel
                
                # Load vector store and embedding model
                vector_store = VectorStore(
                    embedding_dim=config.EMBEDDING_DIMENSION,
                    index_path=config.FAISS_INDEX_FILE
                )
                
                # ✅ FIXED: Try to load, create fresh if doesn't exist
                try:
                    vector_store.load(config.FAISS_INDEX_FILE)
                    print(f"[VIDEO] ✓ Loaded existing FAISS index")
                except Exception as load_err:
                    print(f"[VIDEO] ℹ️  FAISS index not found, creating fresh...")
                    vector_store.initialize_index()
                    print(f"[VIDEO] ✓ Fresh FAISS index created")
                
                embedding_model = EmbeddingModel(config.EMBEDDINGS_MODEL)
                
                # Extract text from chunks
                chunk_texts = [chunk["text"] for chunk in chunks]
                
                # Generate embeddings
                embeddings = embedding_model.embed_texts(chunk_texts)
                
                # ✅ FIXED: Create metadata list with CORRECT structure
                # Make sure video_id is at ROOT level, not nested
                metadata_list = []
                for idx, chunk in enumerate(chunks):
                    meta = {
                        "chunk_id": chunk.get("chunk_id", f"vid_{video_id[:8]}_{idx:04d}"),
                        "source": "video",
                        "video_id": video_id,  # ← ROOT level
                        "filename": file.filename,
                        "text": chunk.get("text", ""),
                    }
                    # Also add nested for compatibility
                    if "metadata" in chunk:
                        meta["metadata"] = chunk["metadata"]
                    metadata_list.append(meta)
                    
                    # ✅ DEBUG: Show what we're adding
                    if idx < 2:
                        print(f"[VIDEO] Chunk {idx}: video_id={meta['video_id']}, text_len={len(meta['text'])}")
                
                # Add to FAISS
                print(f"[VIDEO] Adding {len(metadata_list)} chunks to FAISS...")
                vector_store.add_embeddings(embeddings, metadata_list)
                vector_store.save(config.FAISS_INDEX_FILE)
                
                print(f"[VIDEO] ✓ Added {len(chunks)} chunks to FAISS")
                print(f"[VIDEO] ✓ FAISS now contains {vector_store.index.ntotal} total vectors")
                print(f"[VIDEO] ✓ Video chunks stored with video_id: {video_id}")
                
                # ✅ CRITICAL FIX: Reload the shared retriever's vector_store
                # so that subsequent queries see the newly added chunks
                try:
                    if hasattr(pipeline, 'retriever') and hasattr(pipeline.retriever, 'vector_store'):
                        print(f"[VIDEO] Reloading shared vector_store in retriever...")
                        pipeline.retriever.vector_store.load(config.FAISS_INDEX_FILE)
                        print(f"[VIDEO] ✓ Shared vector_store reloaded ({len(pipeline.retriever.vector_store.metadata)} docs total)")
                except Exception as reload_err:
                    print(f"[VIDEO] ⚠️  Could not reload shared vector_store: {reload_err}")
                
            except Exception as embed_err:
                print(f"[VIDEO] ⚠️  Warning: Failed to embed video chunks: {embed_err}")
                # Don't fail upload if embedding fails - video is still transcribed
                import traceback
                traceback.print_exc()
            
            # Mark as indexed
            video_handler.mark_indexed(video_id, len(chunks))
            
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            
            return {
                "status": "success",
                "video_id": video_id,
                "filename": file.filename,
                "chunks": len(chunks),
                "transcript_length": len(transcript),
                "message": f"Video uploaded and transcribed: {len(chunks)} chunks created and indexed"
            }
        
        except Exception as e:
            print(f"[ERROR] Video upload failed: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}, 500
    
    @app.get("/video/list")
    async def list_videos():
        """Get all uploaded videos."""
        try:
            global video_handler
            if video_handler is None:
                video_handler = get_video_handler()
            
            videos = video_handler.get_videos()
            return {
                "status": "success",
                "videos": videos,
                "count": len(videos)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
    
    @app.get("/video/{video_id}")
    async def get_video_info(video_id: str):
        """Get video details."""
        try:
            global video_handler
            if video_handler is None:
                video_handler = get_video_handler()
            
            registry = video_handler.registry
            if video_id not in registry:
                return {"status": "error", "message": "Video not found"}, 404
            
            return {
                "status": "success",
                "video": registry[video_id]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
    
    # ============================================================
    # USER INTERFACE ENDPOINTS
    # ============================================================
    
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the user chatbot UI."""
        try:
            with open("chatbot_ui_enhanced.html", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return """
            <html>
            <body style="font-family: Arial; padding: 20px; color: #d32f2f;">
                <h1>⚠️ Chatbot UI Not Found</h1>
                <p>File: chatbot_ui_enhanced.html is missing.</p>
                <p>Try the <a href="/docs">API Documentation</a> instead.</p>
                <p>Or use the <a href="/admin">Admin Dashboard</a>.</p>
            </body>
            </html>
            """
    
    @app.get("/index.html", response_class=HTMLResponse)
    async def index():
        """Alias for root chatbot UI."""
        try:
            with open("chatbot_ui_enhanced.html", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return """
            <html>
            <body style="font-family: Arial; padding: 20px; color: #d32f2f;">
                <h1>⚠️ Chatbot UI Not Found</h1>
                <p>File: chatbot_ui_enhanced.html is missing.</p>
                <p>Visit <a href="/">home</a> instead.</p>
            </body>
            </html>
            """
    
    @app.post("/ask", response_model=QueryResponse)
    async def ask(request: QueryRequest, req: Request):
        """
        Process a query through the guarded retrieval pipeline.
        with safe attribute access and comprehensive error handling.
        
        NEW: Supports optional video_id for video-specific retrieval.
        NEW: Supports session_id for multi-turn conversations.
        """
        start_time = time.time()
        ip_address = req.client.host if req.client else "unknown"
        
        print(f"\n[API] /ask endpoint called")
        print(f"[API] Query: {request.query[:100]}")
        if request.video_id:
            print(f"[API] Video ID: {request.video_id}")
        
        # ✅ FIXED: Session Management
        from chat_session_manager import get_session_manager
        session_manager = get_session_manager()
        
        # ✅ CRITICAL FIX: DO NOT auto-create sessions in /ask endpoint
        # Sessions must ONLY be created when user clicks "New Chat"
        # If no session_id provided, return error - user must create one first
        if not request.session_id:
            return QueryResponse(
                success=False,
                message="No session provided. Please start a new chat.",
                compliance_allowed=False
            )
        
        print(f"[API] Using session: {request.session_id}")
        
        # Load session to get context
        session = session_manager.get_session(request.session_id)
        if not session:
            return QueryResponse(
                success=False,
                message=f"Session not found: {request.session_id}",
                compliance_allowed=False
            )
        
        print(f"[API] Session loaded: {len(session.messages)} messages in history")
        
        # If video mode requested, set it
        if request.video_id and request.video_id != session.active_video_id:
            session_manager.set_active_video(request.session_id, request.video_id)
        
        try:
            # ✅ NEW: Extract conversation context from CURRENT session ONLY
            # Limit to 5 messages (2.5 pairs) for better isolation between sessions
            conversation_context = session_manager.get_context_string(
                request.session_id, 
                max_messages=5  # Reduced from 10 for better session isolation
            )
            if conversation_context:
                print(f"[API] ✓ Using context from session {request.session_id}: {len(conversation_context)} chars")
            else:
                print(f"[API] ℹ️ New/empty session {request.session_id}: no prior context available")
            
             # Call pipeline with optional video_id AND conversation context
            print(f"[API] Calling pipeline.process()...")
            
            # ✅ NEW: Use project-aware pipeline if available
            active_pipeline = config.PROJECT_PIPELINE if hasattr(config, 'PROJECT_PIPELINE') else pipeline
            
            if hasattr(active_pipeline, 'process') and 'session_id' in str(active_pipeline.process.__code__.co_varnames):
                # Use project-aware pipeline with project support
                result = active_pipeline.process(
                    query=request.query,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    video_id=request.video_id
                )
            else:
                # Fall back to original pipeline
                result = pipeline.process(
                    query=request.query,
                    user_id=request.user_id,
                    ip_address=ip_address,
                    video_id=request.video_id,
                    conversation_context=conversation_context,
                    session_id=request.session_id
                )
            
            # ✅ VALIDATION: Check result type and extract safely
            print(f"[API] Checking result object...")
            
            # Handle both dict responses (from project pipeline) and dataclass responses (from original pipeline)
            if isinstance(result, dict):
                # Project pipeline returns dict
                print(f"[API] ✓ Result is dict (project pipeline)")
                llm_response_text = result.get('answer', result.get('llm_response', '')) or ""
                compliance_allowed = result.get('compliance_allowed', False)
                retrieved_documents = result.get('retrieved_documents', []) or []
                audit_log_id = result.get('audit_log_id', 0) or 0
                success = result.get('success', False)
                response_valid = result.get('response_valid', False)
                message = result.get('message', "") or ""
                validation_issues = result.get('validation_issues', []) or []
                is_project_mode = result.get('project_mode', False)
            else:
                # Original pipeline returns dataclass
                print(f"[API] ✓ Result is {type(result).__name__} (original pipeline)")
                
                if not hasattr(result, 'llm_response'):
                    error_msg = f"Pipeline returned incompatible object type: {type(result).__name__}"
                    print(f"[API] ✗ {error_msg}")
                    print(f"[API] Result attributes: {dir(result)}")
                    raise AttributeError(error_msg)
                
                if not hasattr(result, 'retrieved_documents'):
                    error_msg = "Pipeline result missing 'retrieved_documents' attribute"
                    print(f"[API] ✗ {error_msg}")
                    raise AttributeError(error_msg)
                
                llm_response_text = getattr(result, 'llm_response', None) or ""
                compliance_allowed = getattr(result, 'compliance_allowed', False)
                retrieved_documents = getattr(result, 'retrieved_documents', []) or []
                audit_log_id = getattr(result, 'audit_log_id', 0) or 0
                success = getattr(result, 'success', False)
                response_valid = getattr(result, 'response_valid', False)
                message = getattr(result, 'message', "") or ""
                validation_issues = getattr(result, 'validation_issues', []) or []
                is_project_mode = False
            
            # Extract citations from retrieved documents
            citations = []
            if retrieved_documents:
                try:
                    citations = [
                        {
                            "document": doc.get("source", "Unknown") if isinstance(doc, dict) else "Unknown",
                            "page": doc.get("page", 0) if isinstance(doc, dict) else 0,
                            "snippet": (doc.get("content", "")[:100] if isinstance(doc, dict) else "")
                        }
                        for doc in retrieved_documents[:3]
                    ]
                except Exception as cite_err:
                    print(f"[API] Warning: Citation extraction failed: {cite_err}")
                    citations = []
            
            # Determine compliance status
            compliance_status = "approved" if compliance_allowed else "blocked"
            
            # DEBUG: Log the full response
            print(f"\n[RESPONSE DEBUG]")
            print(f"  Message: {(message[:100] if message else 'EMPTY')}...")
            print(f"  LLM Response: {(llm_response_text[:100] if llm_response_text else 'EMPTY')}...")
            print(f"  Success: {success}")
            print(f"  Compliance: {compliance_allowed}")
            print(f"  Docs Retrieved: {len(retrieved_documents)}")
            
            # Build response with safe defaults
            response_dict = {
                "success": success,
                "message": message,
                "compliance_allowed": compliance_allowed,
                "response_valid": response_valid if response_valid is not None else False,
                "retrieved_documents": retrieved_documents,
                "validation_issues": validation_issues,
                "audit_log_id": audit_log_id,
                "timestamp": datetime.utcnow().isoformat(),
                "answer": llm_response_text,
                "answer_citations": citations,
                "compliance_status": compliance_status,
                "processing_details": {
                    "processing_time_ms": int((time.time() - start_time) * 1000),
                    "documents_used": len(retrieved_documents),
                    "validation_passed": response_valid if response_valid is not None else False,
                    "compliance_issues": validation_issues
                }
            }
            
            # ✅ COMPLIANCE ENFORCEMENT: Format response with 6-section structure
            formatted_response = enforce_compliance_on_response(
                question=request.query,
                llm_response=llm_response_text,
                retrieved_documents=retrieved_documents
            )
            response_dict["answer"] = formatted_response
            
            # ✅ NEW: Save to session
            try:
                compliance_decision = {
                    "allowed": compliance_allowed,
                    "status": compliance_status,
                    "issues": validation_issues
                }
                
                session_manager.add_message_to_session(
                    session_id=request.session_id,
                    role="user",
                    content=request.query,
                    retrieved_docs=retrieved_documents,
                    compliance_decision=compliance_decision,
                    video_id=request.video_id
                )
                
                session_manager.add_message_to_session(
                    session_id=request.session_id,
                    role="assistant",
                    content=formatted_response,
                    retrieved_docs=retrieved_documents,
                    compliance_decision=compliance_decision,
                    video_id=request.video_id
                )
                
                response_dict["session_id"] = request.session_id
                print(f"[API] ✓ Saved to session {request.session_id}")
            except Exception as session_err:
                print(f"[API] ⚠️ Session save failed: {session_err}")
            
            print(f"[API] ✓ Response built successfully")
            return QueryResponse(**response_dict)
            
        except AttributeError as attr_err:
            print(f"[API] ✗ Attribute error: {str(attr_err)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Pipeline returned incompatible result: {str(attr_err)}"
            )
        
        except Exception as e:
            print(f"[API] ✗ Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"API error: {str(e)}"
            )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/audit/stats")
    async def audit_stats(days: int = 7):
        """Get audit statistics for the last N days."""
        try:
            stats = pipeline.audit_logger.get_statistics(days=days)
            return {
                "status": "ok",
                "statistics": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")
    
    @app.get("/audit/logs")
    async def get_audit_logs(user_id: Optional[str] = None, days: int = 7, limit: int = 100):
        """Retrieve audit logs (authorized users only in production)."""
        try:
            logs = pipeline.audit_logger.retrieve_logs(user_id=user_id, days=days, limit=limit)
            return {
                "status": "ok",
                "logs": logs,
                "count": len(logs),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Audit error: {str(e)}")
    
    # ============================================================
    # SESSION MANAGEMENT ENDPOINTS (NEW)
    # ============================================================
    
    @app.get("/sessions")
    async def list_sessions(user_id: str = "default_user"):
        """List all sessions for the user."""
        try:
            from chat_session_manager import get_session_manager
            session_manager = get_session_manager()
            sessions = session_manager.list_sessions(user_id=user_id)
            return {
                "status": "ok",
                "sessions": sessions,
                "count": len(sessions),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Session list error: {str(e)}")
    
    @app.post("/sessions/new")
    async def create_new_session(user_id: str = "default_user"):
        """Create a new chat session."""
        try:
            from chat_session_manager import get_session_manager
            session_manager = get_session_manager()
            session_id = session_manager.create_session(user_id=user_id)
            return {
                "status": "created",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Session creation error: {str(e)}")
    
    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str):
        """Retrieve a specific session."""
        try:
            from chat_session_manager import get_session_manager
            session_manager = get_session_manager()
            session = session_manager.get_session(session_id)
            
            if not session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
            
            return {
                "status": "ok",
                "session": session.to_dict(),
                "timestamp": datetime.utcnow().isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Session retrieval error: {str(e)}")
    
    @app.get("/sessions/{session_id}/messages")
    async def get_session_messages(session_id: str):
        """Retrieve messages from a session."""
        try:
            from chat_session_manager import get_session_manager
            session_manager = get_session_manager()
            session = session_manager.get_session(session_id)
            
            if not session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
            
            return {
                "status": "ok",
                "messages": session.messages,
                "count": len(session.messages),
                "timestamp": datetime.utcnow().isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Message retrieval error: {str(e)}")
    
    @app.get("/docs/{doc_name}")
    async def get_document(doc_name: str):
        """
        Retrieve document content for display in UI.
        Searches in Data1/Data/ folder for policy documents.
        """
        try:
            # Security: Prevent directory traversal
            if ".." in doc_name or "/" in doc_name or "\\" in doc_name:
                raise HTTPException(status_code=400, detail="Invalid document name")
            
            # Try multiple document locations
            possible_paths = [
                Path("Data1/Data") / doc_name,
                Path("Data1/Data") / f"{doc_name}.md",
                Path("Data1/Data") / f"{doc_name}.csv",
                Path("Data1/Data") / f"{doc_name}.txt",
                Path("Data1/Data") / f"{doc_name}.pdf",
            ]
            
            doc_path = None
            for path in possible_paths:
                if path.exists():
                    doc_path = path
                    break
            
            if not doc_path:
                raise HTTPException(status_code=404, detail=f"Document '{doc_name}' not found")
            
            # Read and return document content
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "status": "ok",
                "document": doc_name,
                "content": content,
                "path": str(doc_path)
            }
        
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving document: {str(e)}")
    
    @app.get("/docs/list")
    async def list_documents():
        """List available policy documents."""
        try:
            data_dir = Path("Data1/Data")
            if not data_dir.exists():
                return {"documents": []}
            
            # Find all relevant documents
            documents = []
            for ext in ['*.md', '*.csv', '*.txt', '*.pdf']:
                for file in data_dir.glob(ext):
                    documents.append(file.name)
            
            return {
                "status": "ok",
                "documents": sorted(documents)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")
    
    # ============================================================
    # ADMIN ENDPOINTS
    # ============================================================
    
    @app.get("/admin")
    async def admin_dashboard():
        """Serve admin dashboard HTML."""
        return HTMLResponse(get_admin_dashboard_html())
    
    @app.post("/admin/documents/upload")
    async def upload_document(
        file: UploadFile = File(...),
        document_name: str = Form(...),
        document_type: str = Form("Internal"),
        version: str = Form("v1.0"),
        background_tasks: BackgroundTasks = BackgroundTasks()
    ):
        """Admin endpoint to upload documents with duplicate detection."""
        try:
            valid_types = ["SOP", "Policy", "Internal", "Technical"]
            if document_type not in valid_types:
                raise HTTPException(status_code=400, detail=f"Invalid type: {', '.join(valid_types)}")
            
            # Check for duplicate document
            doc_key = f"{document_name}||{version}"
            if doc_key in existing_documents:
                raise HTTPException(
                    status_code=409, 
                    detail=f"Document '{document_name}' v{version} already exists. Cannot upload duplicate."
                )
            
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            
            upload_id = str(uuid.uuid4())[:8]
            file_ext = Path(file.filename).suffix
            saved_filename = f"{document_name}_{version}_{upload_id}{file_ext}"
            file_path = upload_dir / saved_filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Track active upload for potential cancellation
            active_uploads[upload_id] = {"file_path": str(file_path), "cancelled": False}
            
            # Register document as existing
            existing_documents[doc_key] = str(file_path)
            
            print(f"[✓] File uploaded: {file_path}")
            background_tasks.add_task(process_document_background, str(file_path), document_name, document_type, version, upload_id)
            
            return {
                "status": "accepted",
                "message": f"Document '{document_name}' v{version} uploaded",
                "upload_id": upload_id,
                "file_path": str(file_path)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    @app.post("/admin/documents/cancel/{upload_id}")
    async def cancel_upload(upload_id: str):
        """Cancel an in-progress or stuck upload - more robust handling."""
        print(f"\n[CANCEL] Attempting to cancel upload: {upload_id}")
        print(f"[CANCEL] Active uploads: {list(active_uploads.keys())}")
        print(f"[CANCEL] Upload progress IDs: {list(upload_progress.keys())}")
        
        file_deleted = False
        doc_cleaned = False
        
        try:
            # Case 1: Upload is still active (in progress)
            if upload_id in active_uploads:
                print(f"[CANCEL] Found in active_uploads (still processing)")
                
                # Mark as cancelled
                active_uploads[upload_id]["cancelled"] = True
                upload_progress[upload_id] = {"progress": 0, "status": "cancelled"}
                
                # Delete the uploaded file
                file_path = active_uploads[upload_id].get("file_path")
                if file_path and Path(file_path).exists():
                    try:
                        Path(file_path).unlink()
                        print(f"[✓] File deleted: {file_path}")
                        file_deleted = True
                    except Exception as e:
                        print(f"[!] Could not delete file: {e}")
                
                # Clean up active upload entry
                del active_uploads[upload_id]
                
                print(f"[✓] Upload {upload_id} cancelled successfully")
                return {
                    "status": "cancelled",
                    "message": f"Upload {upload_id} has been cancelled",
                    "upload_id": upload_id,
                    "file_deleted": file_deleted
                }
            
            # Case 2: Upload already completed but stuck in progress
            elif upload_id in upload_progress:
                current_status = upload_progress[upload_id].get("status")
                print(f"[CANCEL] Found in upload_progress with status: {current_status}")
                
                # Try to delete file from existing_documents registry
                for doc_key in list(existing_documents.keys()):
                    doc_path = existing_documents[doc_key]
                    if Path(doc_path).exists():
                        try:
                            Path(doc_path).unlink()
                            print(f"[✓] Deleted document file: {doc_path}")
                            file_deleted = True
                            del existing_documents[doc_key]
                            doc_cleaned = True
                        except Exception as e:
                            print(f"[!] Could not delete document: {e}")
                
                # Mark as cancelled anyway
                upload_progress[upload_id] = {"progress": 0, "status": "cancelled"}
                
                print(f"[✓] Upload {upload_id} marked as cancelled (was {current_status})")
                return {
                    "status": "cancelled",
                    "message": f"Upload cancelled (was {current_status})",
                    "upload_id": upload_id,
                    "file_deleted": file_deleted,
                    "doc_cleaned": doc_cleaned
                }
            
            # Case 3: Upload ID not found anywhere
            else:
                print(f"[CANCEL] Upload ID {upload_id} not found in any registry")
                raise HTTPException(
                    status_code=404,
                    detail=f"Upload ID '{upload_id}' not found. Try refreshing the page."
                )
        
        except HTTPException:
            raise
        except Exception as e:
            print(f"[ERROR] Cancellation failed: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Cancellation failed: {str(e)}")
    
    @app.get("/admin/documents/existing")
    async def get_existing_documents():
        """Get list of all existing documents (for duplicate checking)."""
        existing_list = []
        for key in existing_documents.keys():
            doc_name, version = key.split("||")
            existing_list.append({"name": doc_name, "version": version})
        
        return {
            "status": "ok",
            "documents": existing_list,
            "count": len(existing_list)
        }
    
    @app.get("/admin/upload-status/{upload_id}")
    async def get_upload_status(upload_id: str):
        """Check document processing status - properly handles FAILED state."""
        progress_data = upload_progress.get(upload_id, {"progress": 0, "status": "processing"})
        status = progress_data.get("status", "processing")
        
        # ✅ CRITICAL: Return full status object including errors
        response = {
            "status": status,
            "upload_id": upload_id,
            "progress": progress_data.get("progress", 0)
        }
        
        # If there's an error, include it in response so frontend can stop polling
        if status == "error" and "error" in progress_data:
            response["error"] = progress_data.get("error")
            response["error_type"] = progress_data.get("error_type", "UnknownError")
            print(f"[STATUS] {upload_id} returning ERROR status: {response['error']}")
        
        return response
    
    # ============================================================
    # PROJECT UPDATES ENDPOINTS (ENTERPRISE FEATURE - NEW)
    # ============================================================
    
    @app.get("/api/projects/list")
    async def list_projects():
        """List all available projects."""
        try:
            if not hasattr(config, 'PROJECT_MANAGER'):
                return {"projects": [], "count": 0, "message": "Project system not initialized"}
            
            project_manager = config.PROJECT_MANAGER
            projects = project_manager.list_projects()
            
            return {
                "projects": projects,
                "count": len(projects),
                "message": "Projects retrieved successfully"
            }
        except Exception as e:
            print(f"[API] Error listing projects: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/projects/select")
    async def select_project(request: dict):
        """Select a project and enter project mode."""
        try:
            project_name = request.get("project_name")
            session_id = request.get("session_id")
            
            if not hasattr(config, 'PROJECT_MANAGER'):
                raise HTTPException(status_code=500, detail="Project system not initialized")
            
            project_manager = config.PROJECT_MANAGER
            
            # Verify project exists
            if not project_manager.project_exists(project_name):
                raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
            
            # Set session state
            if hasattr(config, 'SESSION_PROJECT_STATE'):
                config.SESSION_PROJECT_STATE.set_project(session_id, project_name)
            
            files = project_manager.get_project_files(project_name)
            
            return {
                "success": True,
                "project_name": project_name,
                "files_count": len(files),
                "message": f"Entered project mode for '{project_name}'"
            }
        except HTTPException:
            raise
        except Exception as e:
            print(f"[API] Error selecting project: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/projects/upload")
    async def upload_project_files(project_name: str = Form(...), 
                                   files: list = File(...)):
        """Upload project files (manual upload)."""
        try:
            if not hasattr(config, 'PROJECT_MANAGER'):
                raise HTTPException(status_code=500, detail="Project system not initialized")
            
            project_manager = config.PROJECT_MANAGER
            uploaded_count = 0
            
            for file in files:
                if file.filename.endswith(('.md', '.txt')):
                    content = await file.read()
                    content_str = content.decode('utf-8')
                    
                    if project_manager.save_project_file(project_name, file.filename, content_str):
                        uploaded_count += 1
            
            # Re-index if ingestion available
            if hasattr(config, 'INGESTION_PIPELINE') and hasattr(config, 'VECTOR_MANAGER'):
                ingestion = config.INGESTION_PIPELINE
                vector_manager = config.VECTOR_MANAGER
                
                chunks = ingestion.ingest_project(project_name)
                if chunks:
                    vector_manager.remove_project_vectors(project_name)
                    vectors_added = vector_manager.add_project_vectors(project_name, chunks)
                    print(f"[API] Indexed {vectors_added} vectors for {project_name}")
            
            return {
                "success": True,
                "project_name": project_name,
                "files_uploaded": uploaded_count,
                "message": f"Uploaded {uploaded_count} files to '{project_name}'"
            }
        except Exception as e:
            print(f"[API] Error uploading project: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/projects/exit")
    async def exit_project_mode(request: dict):
        """Exit project mode."""
        try:
            session_id = request.get("session_id")
            
            if hasattr(config, 'SESSION_PROJECT_STATE'):
                config.SESSION_PROJECT_STATE.set_project(session_id, None)
            
            return {
                "success": True,
                "message": "Exited project mode"
            }
        except Exception as e:
            print(f"[API] Error exiting project mode: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/projects/sync-status/{project_name}")
    async def get_sync_status(project_name: str):
        """Get last sync status for a project."""
        try:
            if not hasattr(config, 'UPDATE_LOGGER'):
                return {"status": "unknown", "message": "No sync history"}
            
            update_logger = config.UPDATE_LOGGER
            log_entry = update_logger.get_project_log(project_name)
            
            if not log_entry:
                return {"status": "never", "message": f"No sync history for {project_name}"}
            
            return log_entry
        except Exception as e:
            print(f"[API] Error getting sync status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return app



def process_document_background(file_path: str, document_name: str, document_type: str, version: str, upload_id: str):
    """Background task to ingest documents into vector store with full error handling."""
    print(f"\n[PROCESS] Starting REAL ingestion for {document_name} v{version}")
    print(f"  File: {file_path}")
    print(f"  Type: {document_type}")
    print(f"  Upload ID: {upload_id}")
    
    # Initialize progress immediately
    if upload_id not in upload_progress:
        upload_progress[upload_id] = {"progress": 0, "status": "processing"}
    
    try:
        # ✅ STEP 1: Health check - verify config is loaded
        print("[INGEST] Checking configuration...")
        if not hasattr(config, "EMBEDDING_DIMENSION"):
            raise RuntimeError("Config not loaded: EMBEDDING_DIMENSION missing")
        if not hasattr(config, "FAISS_INDEX_FILE"):
            raise RuntimeError("Config not loaded: FAISS_INDEX_FILE missing")
        if not hasattr(config, "EMBEDDINGS_MODEL"):
            raise RuntimeError("Config not loaded: EMBEDDINGS_MODEL missing")
        print(f"[INGEST] Config verified ✓")
        print(f"[UPLOAD STATUS] {upload_id} → initializing")
        
        # Import real ingestion pipeline
        from real_ingestion import RealDocumentIngester
        from vector_store import VectorStore, EmbeddingModel
        
        # STEP 2: Initialize ingestion components (10% progress)
        print("[INGEST] Initializing ingestion components...")
        upload_progress[upload_id] = {"progress": 10, "status": "Initializing..."}
        print(f"[UPLOAD STATUS] {upload_id} → initializing (10%)")
        
        # Load vector store and embedding model
        vector_store = VectorStore(
            embedding_dim=config.EMBEDDING_DIMENSION,
            index_path=config.FAISS_INDEX_FILE
        )
        vector_store.load(config.FAISS_INDEX_FILE)
        print(f"[INGEST] Vector store loaded: {len(vector_store.metadata)} docs")
        
        embedding_model = EmbeddingModel(config.EMBEDDINGS_MODEL)
        print(f"[INGEST] Embedding model loaded")
        
        # Create ingester
        ingester = RealDocumentIngester(vector_store, embedding_model)
        
        # STEP 3: Extract text (20% progress)
        print("[INGEST] Extracting text...")
        upload_progress[upload_id] = {"progress": 20, "status": "Extracting text..."}
        print(f"[UPLOAD STATUS] {upload_id} → extracting (20%)")
        text, text_length = ingester.extract_text(file_path, document_type)
        
        if text_length == 0:
            raise ValueError("Text extraction returned 0 characters - file may be empty or corrupt")
        print(f"[INGEST] Extracted {text_length} characters")
        
        # STEP 4: Chunk text (40% progress)
        print("[INGEST] Chunking document...")
        upload_progress[upload_id] = {"progress": 40, "status": "Chunking document..."}
        print(f"[UPLOAD STATUS] {upload_id} → chunking (40%)")
        chunks = ingester.chunk_text(text, document_name, version, document_type)
        
        if not chunks:
            raise ValueError("No chunks created from document")
        print(f"[INGEST] Created {len(chunks)} chunks")
        
        # STEP 5: Generate embeddings (60% progress)
        print("[INGEST] Generating embeddings...")
        upload_progress[upload_id] = {"progress": 60, "status": "Generating embeddings..."}
        print(f"[UPLOAD STATUS] {upload_id} → embedding (60%)")
        embedding_result = ingester.generate_embeddings(chunks)
        
        if embedding_result is None:
            raise ValueError("Embedding generation failed")
        
        embeddings, embedding_dim = embedding_result
        print(f"[INGEST] Generated {len(embeddings)} embeddings (dim={embedding_dim})")
        
        # STEP 6: Insert into vector store (80% progress)
        print("[INGEST] Inserting into FAISS index...")
        upload_progress[upload_id] = {"progress": 80, "status": "Indexing vectors..."}
        print(f"[UPLOAD STATUS] {upload_id} → inserting (80%)")
        
        if not ingester.insert_into_vector_store(chunks, embeddings):
            raise ValueError("Failed to insert vectors into FAISS index")
        print(f"[INGEST] Inserted into FAISS")
        
        # STEP 7: Finalize (100% progress)
        print("[INGEST] Finalizing...")
        upload_progress[upload_id] = {"progress": 100, "status": "Finalizing..."}
        print(f"[UPLOAD STATUS] {upload_id} → finalizing (90%)")
        
        # ✅ SUCCESS: Mark as completed
        print(f"[✓] Document ingestion complete: {document_name}")
        print(f"[✓] Ingested {len(chunks)} chunks into vector store")
        print(f"[✓] FAISS index now contains {vector_store.index.ntotal} vectors")
        
        upload_progress[upload_id] = {"progress": 100, "status": "completed"}
        print(f"[UPLOAD STATUS] {upload_id} → completed (100%)")
        
        # Clean up active upload entry (job finished)
        if upload_id in active_uploads:
            del active_uploads[upload_id]
        
        print(f"[✓] Upload {upload_id} marked as completed")
        
    except Exception as e:
        # ❌ FAILURE: Capture error and update status
        error_msg = str(e)
        print(f"\n[ERROR] REAL ingestion failed: {error_msg}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        traceback.print_exc()
        
        # ✅ CRITICAL: Update status to FAILED so frontend stops polling
        upload_progress[upload_id] = {
            "progress": 0, 
            "status": "error",
            "error": error_msg,
            "error_type": type(e).__name__
        }
        print(f"[UPLOAD STATUS] {upload_id} → error: {error_msg}")
        
        # Clean up on error
        doc_key = f"{document_name}||{version}"
        if doc_key in existing_documents:
            del existing_documents[doc_key]
            print(f"[CLEANUP] Removed {doc_key} from existing documents")
        
        if upload_id in active_uploads:
            del active_uploads[upload_id]
            print(f"[CLEANUP] Removed {upload_id} from active uploads")
        
        print(f"[CLEANUP] Error cleanup completed")
        chunks = ingester.chunk_text(text, document_name, version, document_type)
        
        if not chunks:
            raise ValueError("No chunks created from document")
        
        # Step 3: Generate embeddings (60% progress)
        print("[INGEST] Generating embeddings...")
        upload_progress[upload_id] = {"progress": 60, "status": "Generating embeddings..."}
        embedding_result = ingester.generate_embeddings(chunks)
        
        if embedding_result is None:
            raise ValueError("Embedding generation failed")
        
        embeddings, embedding_dim = embedding_result
        
        # Step 4: Insert into vector store (80% progress)
        print("[INGEST] Inserting into FAISS index...")
        upload_progress[upload_id] = {"progress": 80, "status": "Indexing vectors..."}
        
        if not ingester.insert_into_vector_store(chunks, embeddings):
            raise ValueError("Failed to insert vectors into FAISS index")
        
        # Step 5: Finalize (100% progress)
        print("[INGEST] Finalizing...")
        upload_progress[upload_id] = {"progress": 100, "status": "Finalizing..."}
        
        # Processing completed successfully
        print(f"[✓] Document ingestion complete: {document_name}")
        print(f"[✓] Ingested {len(chunks)} chunks into vector store")
        print(f"[✓] FAISS index now contains {vector_store.index.ntotal} vectors")
        
        upload_progress[upload_id] = {"progress": 100, "status": "completed"}
        
        # Clean up active upload entry (job finished)
        if upload_id in active_uploads:
            del active_uploads[upload_id]
        
        print(f"[✓] Upload {upload_id} marked as completed")
        
    except Exception as e:
        print(f"[ERROR] REAL ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        
        upload_progress[upload_id] = {
            "progress": 0, 
            "status": "error", 
            "error": str(e)
        }
        
        # Clean up on error
        doc_key = f"{document_name}||{version}"
        if doc_key in existing_documents:
            del existing_documents[doc_key]
        
        if upload_id in active_uploads:
            del active_uploads[upload_id]
        
        print(f"[CLEANUP] Error cleanup completed")


def get_admin_dashboard_html() -> str:
    """Return HTML for admin dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - Document Management</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 40px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .dashboard { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
        @media (max-width: 768px) { .dashboard { grid-template-columns: 1fr; } }
        .card { background: white; border-radius: 10px; padding: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }
        .card h2 { color: #333; margin-bottom: 20px; font-size: 1.5em; border-bottom: 3px solid #667eea; padding-bottom: 10px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; color: #555; font-weight: 600; margin-bottom: 8px; }
        input, select { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 5px; font-size: 1em; }
        input:focus, select:focus { outline: none; border-color: #667eea; }
        .file-input-label { display: block; padding: 40px 20px; border: 2px dashed #667eea; border-radius: 8px; text-align: center; cursor: pointer; background: #f8f9ff; }
        input[type="file"] { display: none; }
        button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 5px; font-weight: 600; cursor: pointer; width: 100%; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102,126,234,0.4); }
        .status-item { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #667eea; }
        .status-item.success { border-left-color: #28a745; background: #d4edda; }
        .status-item.error { border-left-color: #dc3545; background: #f8d7da; }
        .info-box { background: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px; border-radius: 4px; margin-bottom: 20px; font-size: 0.9em; color: #1565c0; }
        .history-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #e0e0e0; }
        .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: 600; }
        .badge.processing { background: #fff3cd; color: #856404; }
        .badge.cancelled { background: #f8d7da; color: #721c24; }
        .badge.success { background: #d4edda; color: #155724; }
        .btn-cancel { background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 0.85em; cursor: pointer; }
        .btn-cancel:hover { background: #c82333; }
        .progress-container { margin: 15px 0; }
        .progress-bar { width: 100%; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; margin-bottom: 8px; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); width: 0%; transition: width 0.3s ease; }
        .progress-text { display: flex; justify-content: space-between; font-size: 0.85em; color: #666; }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid #f3f3f3; border-top: 2px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; vertical-align: middle; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 Document Management</h1>
            <p>Upload and manage compliance documents</p>
        </div>
        
        <div class="dashboard">
            <div class="card">
                <h2>📤 Upload Document</h2>
                <div class="info-box">ℹ️ Upload policy documents, SOPs, or internal guidelines</div>
                
                <form id="uploadForm">
                    <div class="form-group">
                        <label for="documentName">Document Name *</label>
                        <input type="text" id="documentName" placeholder="e.g., Compliance_Policy" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="documentType">Document Type *</label>
                        <select id="documentType" required>
                            <option value="">-- Select Type --</option>
                            <option value="SOP">SOP (Standard Operating Procedure)</option>
                            <option value="Policy">Policy</option>
                            <option value="Internal">Internal Document</option>
                            <option value="Technical">Technical</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="version">Version *</label>
                        <input type="text" id="version" placeholder="e.g., v1.0" value="v1.0" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="fileInput">Select File *</label>
                        <div class="file-input-label" id="fileInputLabel">
                            <input type="file" id="fileInput" accept=".pdf,.md,.txt,.docx" required>
                            <div>
                                <p style="font-size: 1.2em; margin-bottom: 10px;">📁 Drop file here or click</p>
                                <p style="font-size: 0.9em; color: #666;">Supported: PDF, MD, TXT, DOCX</p>
                            </div>
                        </div>
                    </div>
                    
                    <button type="submit">Upload & Process</button>
                    <button type="button" style="background: #6c757d; margin-top: 10px;" onclick="clearForm()">Clear</button>
                </form>
                
                <div id="uploadStatus"></div>
            </div>
            
            <div class="card">
                <h2>📊 Upload History</h2>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <div></div>
                    <button type="button" style="background: #6c757d; padding: 8px 15px; font-size: 0.9em;" onclick="clearUploadHistory()">🗑️ Clear History</button>
                </div>
                <div id="historyContainer" style="margin-top: 20px;">
                    <p style="color: #999; text-align: center;">No uploads yet</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let uploadHistory = JSON.parse(localStorage.getItem('uploadHistory') || '[]');
        let existingDocuments = [];
        const fileInputLabel = document.getElementById('fileInputLabel');
        const fileInput = document.getElementById('fileInput');
        let currentUploadId = null;
        
        // Load existing documents on page load
        async function loadExistingDocuments() {
            try {
                const response = await fetch('/admin/documents/existing');
                const result = await response.json();
                existingDocuments = result.documents || [];
            } catch (error) {
                console.warn('Could not load existing documents:', error);
            }
        }
        
        loadExistingDocuments();
        
        // Make the drop zone clickable
        fileInputLabel.addEventListener('click', (e) => {
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });
        
        // Handle file selection via input
        fileInput.addEventListener('change', (e) => {
            if (fileInput.files.length > 0) {
                const fileName = fileInput.files[0].name;
                const fileText = fileInputLabel.querySelector('div');
                fileText.innerHTML = `<p style="font-weight: 600; color: #667eea;">✓ Selected: ${fileName}</p>`;
            }
        });
        
        // Drag and drop handling
        fileInputLabel.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInputLabel.style.background = '#e8ebff';
            fileInputLabel.style.borderColor = '#764ba2';
        });
        
        fileInputLabel.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInputLabel.style.background = '#f8f9ff';
            fileInputLabel.style.borderColor = '#667eea';
        });
        
        fileInputLabel.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInputLabel.style.background = '#f8f9ff';
            fileInputLabel.style.borderColor = '#667eea';
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                const fileName = files[0].name;
                const fileText = fileInputLabel.querySelector('div');
                fileText.innerHTML = `<p style="font-weight: 600; color: #667eea;">✓ Selected: ${fileName}</p>`;
            }
        });
        
        function isDuplicateDocument(name, version) {
            return existingDocuments.some(doc => doc.name === name && doc.version === version);
        }
        
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const documentName = document.getElementById('documentName').value.trim();
            const documentType = document.getElementById('documentType').value;
            const version = document.getElementById('version').value.trim();
            const file = fileInput.files[0];
            
            if (!documentName) { showStatus('error', 'Please enter document name'); return; }
            if (!documentType) { showStatus('error', 'Please select document type'); return; }
            if (!version) { showStatus('error', 'Please enter version'); return; }
            if (!file) { showStatus('error', 'Please select a file'); return; }
            
            // Check for duplicates
            if (isDuplicateDocument(documentName, version)) {
                showStatus('error', `⚠️ Document "${documentName}" v${version} already exists! Cannot upload duplicate.`);
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('document_name', documentName);
            formData.append('document_type', documentType);
            formData.append('version', version);
            
            try {
                showStatus('processing', '⏳ Uploading...');
                const response = await fetch('/admin/documents/upload', { 
                    method: 'POST', 
                    body: formData 
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Upload failed');
                }
                
                const result = await response.json();
                currentUploadId = result.upload_id;
                
                uploadHistory.unshift({
                    id: result.upload_id,
                    name: documentName,
                    type: documentType,
                    version: version,
                    timestamp: new Date().toLocaleString(),
                    status: 'processing'
                });
                localStorage.setItem('uploadHistory', JSON.stringify(uploadHistory));
                
                showStatus('success', `✓ Document "${documentName}" uploaded successfully!`);
                clearForm();
                updateHistory();
                
                // Start polling for progress
                startProgressPolling(result.upload_id);
            } catch (error) {
                showStatus('error', `Error: ${error.message}`);
            }
        });
        
        function startProgressPolling(uploadId) {
            if (pollingIntervals[uploadId]) return; // Already polling
            
            pollingIntervals[uploadId] = setInterval(async () => {
                try {
                    const response = await fetch(`/admin/upload-status/${uploadId}`);
                    const result = await response.json();
                    
                    console.log(`[POLL] ${uploadId}: status=${result.status}, progress=${result.progress}%`);
                    
                    // Update progress in history
                    const item = uploadHistory.find(h => h.id === uploadId);
                    if (item) {
                        if (result.progress !== undefined) {
                            item.progress = result.progress;
                        }
                        
                        // ✅ Handle all status states
                        if (result.status === 'completed') {
                            item.status = 'completed';
                            item.progress = 100;
                            clearInterval(pollingIntervals[uploadId]);
                            delete pollingIntervals[uploadId];
                            console.log(`[POLL] ${uploadId} completed - stopped polling`);
                        } else if (result.status === 'error') {
                            // ✅ CRITICAL: Stop polling on error
                            item.status = 'error';
                            item.error = result.error || 'Unknown error';
                            item.error_type = result.error_type || 'Error';
                            item.progress = 0;
                            clearInterval(pollingIntervals[uploadId]);
                            delete pollingIntervals[uploadId];
                            console.error(`[POLL] ${uploadId} error - stopped polling: ${item.error}`);
                        } else if (result.status === 'cancelled') {
                            item.status = 'cancelled';
                            item.progress = 0;
                            clearInterval(pollingIntervals[uploadId]);
                            delete pollingIntervals[uploadId];
                            console.log(`[POLL] ${uploadId} cancelled - stopped polling`);
                        }
                        
                        localStorage.setItem('uploadHistory', JSON.stringify(uploadHistory));
                        updateHistory();
                    }
                } catch (error) {
                    console.error('Progress poll error:', error);
                }
            }, 500); // Poll every 500ms
        }
        
        async function cancelUpload(uploadId) {
            if (!confirm('Are you sure you want to cancel this upload?')) return;
            
            console.log(`[CANCEL] Attempting to cancel upload: ${uploadId}`);
            
            try {
                const response = await fetch(`/admin/documents/cancel/${uploadId}`, {
                    method: 'POST'
                });
                
                console.log(`[CANCEL] Response status: ${response.status}`);
                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.detail || 'Cancellation failed');
                }
                
                console.log(`[CANCEL] Success:`, result);
                
                // Stop polling immediately
                if (pollingIntervals[uploadId]) {
                    clearInterval(pollingIntervals[uploadId]);
                    delete pollingIntervals[uploadId];
                }
                
                // Update history
                const item = uploadHistory.find(h => h.id === uploadId);
                if (item) {
                    item.status = 'cancelled';
                    item.progress = 0;
                    localStorage.setItem('uploadHistory', JSON.stringify(uploadHistory));
                    updateHistory();
                    console.log(`[CANCEL] Updated UI for ${uploadId}`);
                }
                
                // Show success message
                alert(`✓ Upload cancelled successfully`);
                
            } catch (error) {
                console.error(`[CANCEL] Error:`, error);
                alert(`Error cancelling upload: ${error.message}`);
            }
        }
        
        function showStatus(type, message) {
            const statusDiv = document.getElementById('uploadStatus');
            statusDiv.className = `status-item ${type}`;
            statusDiv.innerHTML = `<p>${message}</p>`;
        }
        
        function clearForm() {
            document.getElementById('uploadForm').reset();
            document.getElementById('uploadStatus').innerHTML = '';
            const fileText = fileInputLabel.querySelector('div');
            fileText.innerHTML = `<div><p style="font-size: 1.2em; margin-bottom: 10px;">📁 Drop file here or click</p><p style="font-size: 0.9em; color: #666;">Supported: PDF, MD, TXT, DOCX</p></div>`;
            currentUploadId = null;
        }
        
        function clearUploadHistory() {
            if (!confirm('Clear all upload history?')) return;
            uploadHistory = [];
            localStorage.setItem('uploadHistory', JSON.stringify(uploadHistory));
            updateHistory();
            showStatus('success', '✓ Upload history cleared');
        }
        
        function updateHistory() {
            const container = document.getElementById('historyContainer');
            if (uploadHistory.length === 0) {
                container.innerHTML = '<p style="color: #999; text-align: center;">No uploads yet</p>';
                return;
            }
            
            let html = '';
            uploadHistory.forEach(item => {
                const progress = item.progress || 0;
                const isCompleted = item.status === 'completed';
                const isProcessing = item.status === 'processing';
                const isCancelled = item.status === 'cancelled';
                const isError = item.status === 'error';
                
                let progressHtml = '';
                let cancelButtonHtml = '';
                let statusBadgeColor = '#fff3cd';
                let statusBadgeTextColor = '#856404';
                let statusText = '⏳ Processing';
                
                if (isCompleted) {
                    statusBadgeColor = '#d4edda';
                    statusBadgeTextColor = '#155724';
                    statusText = '✓ Done';
                } else if (isCancelled) {
                    statusBadgeColor = '#f8d7da';
                    statusBadgeTextColor = '#721c24';
                    statusText = '✗ Cancelled';
                } else if (isError) {
                    // ✅ Show error status clearly
                    statusBadgeColor = '#f8d7da';
                    statusBadgeTextColor = '#721c24';
                    statusText = '✗ Error';
                }
                
                if (isProcessing) {
                    progressHtml = `
                        <div class="progress-container" style="margin-top: 8px;">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${progress}%"></div>
                            </div>
                            <div class="progress-text">
                                <span><span class="spinner"></span>${progress}%</span>
                                <span>${Math.round((100 - progress) / 100 * 5)}s remaining</span>
                            </div>
                        </div>
                    `;
                    cancelButtonHtml = `<button class="btn-cancel" onclick="cancelUpload('${item.id}')">Cancel</button>`;
                } else if (progress > 0 && progress < 100 && !isError) {
                    progressHtml = `
                        <div class="progress-container" style="margin-top: 8px;">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${progress}%"></div>
                            </div>
                            <div class="progress-text">
                                <span><span class="spinner"></span>${progress}%</span>
                                <span>${Math.round((100 - progress) / 100 * 5)}s remaining</span>
                            </div>
                        </div>
                    `;
                } else if (isError) {
                    // ✅ Show error message in history
                    const errorMsg = item.error || 'Unknown error';
                    progressHtml = `
                        <div class="progress-container" style="margin-top: 8px;">
                            <div style="color: #721c24; font-size: 0.85em; padding: 8px; background: #f8d7da; border-radius: 4px;">
                                <strong>Error:</strong> ${errorMsg}
                            </div>
                        </div>
                    `;
                }
                
                html += `
                    <div class="history-item" style="flex-direction: column; align-items: flex-start;">
                        <div style="width: 100%; display: flex; justify-content: space-between; align-items: center;">
                            <div><strong>${item.name}</strong> v${item.version}<br><small style="color: #999;">${item.timestamp}</small></div>
                            <div style="display: flex; gap: 10px; align-items: center;">
                                <span class="badge" style="background: ${statusBadgeColor}; color: ${statusBadgeTextColor};">${statusText}</span>
                                ${cancelButtonHtml}
                            </div>
                        </div>
                        ${progressHtml}
                    </div>
                `;
            });
            container.innerHTML = html;
        }
        
        updateHistory();
    </script>
</body>
</html>
    """


if __name__ == "__main__":
    import uvicorn
    import sys
    from server_utils import PortManager, print_port_diagnostics
    
    print("[START] Initializing API server...")
    
    try:
        # Use system initialization module for proper dependency injection
        print("[STEP 1] Initializing system components with dependency injection...")
        from system_initialization import initialize_system
        pipeline = initialize_system()
        print("[✓] Pipeline initialized successfully")
        
        # Create FastAPI app
        print("\n[STEP 2] Creating FastAPI application...")
        app = create_app(pipeline)
        print("[✓] FastAPI app created")
        
        # Load existing documents for duplicate detection
        print("\n[STEP 3] Loading existing documents...")
        load_existing_documents()
        print("[✓] Document registry initialized")
        
        # ✅ Check port availability BEFORE starting server
        print("\n[STEP 4] Checking port availability...")
        host = config.API_HOST or "0.0.0.0"
        port = config.API_PORT or 8000
        
        if PortManager.is_port_in_use(host, port):
            print(f"✗ Port {port} is already in use")
            print_port_diagnostics(host, port)
            
            # Try to find next free port
            print("  Searching for available ports...")
            free_port = PortManager.find_free_port(host, port)
            
            if free_port:
                print(f"✓ Using available port: {free_port}")
                port = free_port
            else:
                print("\n✗ No free ports available from 8000-8009")
                print("\nOn Windows, kill existing process with:")
                if sys.platform == "win32":
                    proc_info = PortManager.get_process_using_port(port)
                    if proc_info:
                        pid, proc_name = proc_info
                        print(f"  taskkill /PID {pid} /F")
                    else:
                        print(f"  netstat -ano | findstr :{port}")
                        print(f"  taskkill /PID <PID> /F")
                sys.exit(1)
        else:
            print(f"✓ Port {port} is available")
        
        # Start server
        print(f"\n[STEP 5] Starting uvicorn server on port {port}...")
        print("\n" + "="*60)
        print("✓ API Server Starting")
        print("="*60)
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Admin UI: http://localhost:{port}/admin")
        print(f"  Docs: http://localhost:{port}/docs")
        print("="*60 + "\n")
        
        try:
            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level="info"
            )
        except OSError as os_error:
            if "10048" in str(os_error) or "Address already in use" in str(os_error):
                print(f"\n✗ Failed to bind to port {port}")
                print_port_diagnostics(host, port)
                sys.exit(1)
            else:
                raise
    
    except KeyboardInterrupt:
        print("\n[STOP] Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
