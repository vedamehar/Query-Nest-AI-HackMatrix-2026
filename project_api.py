"""
Project Updates API Endpoints
Expose project functionality through FastAPI
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ProjectListResponse(BaseModel):
    """List of available projects"""
    projects: List[str]
    count: int


class ProjectSelectRequest(BaseModel):
    """Request to select a project"""
    project_name: str
    session_id: str


class ProjectSelectResponse(BaseModel):
    """Confirmation of project selection"""
    success: bool
    project_name: str
    message: str


class ProjectUploadResponse(BaseModel):
    """Response from project upload"""
    success: bool
    project_name: str
    files_uploaded: int
    message: str


class ProjectExitResponse(BaseModel):
    """Response from exiting project mode"""
    success: bool
    message: str


class SyncStatusResponse(BaseModel):
    """Status of last sync"""
    project_name: str
    files_processed: int
    vectors_indexed: int
    last_sync: str
    status: str


# ============================================================================
# API ROUTER
# ============================================================================

def create_project_router(dependencies: Dict):
    """
    Create project API router with dependencies injected.
    
    Args:
        dependencies: Dict containing:
            - project_manager
            - update_logger
            - vector_manager
            - embedding_model
            - notion_extractor
            - session_manager
    """
    
    router = APIRouter(prefix="/api/projects", tags=["projects"])
    
    # Extract dependencies
    project_manager = dependencies.get("project_manager")
    update_logger = dependencies.get("update_logger")
    vector_manager = dependencies.get("vector_manager")
    ingestion_pipeline = dependencies.get("ingestion_pipeline")
    notion_extractor = dependencies.get("notion_extractor")
    session_manager = dependencies.get("session_manager")
    
    # ========================================================================
    # ENDPOINT: List available projects
    # ========================================================================
    
    @router.get("/list", response_model=ProjectListResponse)
    async def list_projects():
        """
        Get list of all available projects.
        
        Returns:
            List of project names
        """
        try:
            projects = project_manager.list_projects()
            logger.info(f"[API] Listed {len(projects)} projects")
            
            return ProjectListResponse(
                projects=projects,
                count=len(projects)
            )
        except Exception as e:
            logger.error(f"[API] Error listing projects: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ========================================================================
    # ENDPOINT: Select project (enter project mode)
    # ========================================================================
    
    @router.post("/select", response_model=ProjectSelectResponse)
    async def select_project(request: ProjectSelectRequest):
        """
        Select a project and enter project mode.
        
        Args:
            request: Contains project_name and session_id
        
        Returns:
            Confirmation and project details
        """
        try:
            project_name = request.project_name
            session_id = request.session_id
            
            # Verify project exists
            if not project_manager.project_exists(project_name):
                raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
            
            # Get project files
            files = project_manager.get_project_files(project_name)
            
            # Set session state to project mode
            if session_manager:
                session_manager.set_project_mode(session_id, project_name)
            
            logger.info(f"[API] Selected project '{project_name}' for session {session_id}")
            
            return ProjectSelectResponse(
                success=True,
                project_name=project_name,
                message=f"Entered project mode for '{project_name}'. Asking {len(files)} files."
            )
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[API] Error selecting project: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ========================================================================
    # ENDPOINT: Upload project data (manual upload)
    # ========================================================================
    
    @router.post("/upload", response_model=ProjectUploadResponse)
    async def upload_project(
        project_name: str = Form(...),
        files: List[UploadFile] = File(...)
    ):
        """
        Manually upload project files (Markdown, text).
        
        Args:
            project_name: Name of project
            files: Files to upload
        
        Returns:
            Upload confirmation with file count
        """
        try:
            uploaded_count = 0
            
            # Process each file
            for file in files:
                if file.filename.endswith(('.md', '.txt')):
                    content = await file.read()
                    content_str = content.decode('utf-8')
                    
                    if project_manager.save_project_file(project_name, file.filename, content_str):
                        uploaded_count += 1
                    
                    logger.info(f"[API] Uploaded {file.filename} to {project_name}")
            
            # Ingest and index
            from project_updates import ProjectIngestionPipeline
            ingestion = ProjectIngestionPipeline()
            chunks = ingestion.ingest_project(project_name)
            
            if vector_manager and chunks:
                # Remove old vectors
                vector_manager.remove_project_vectors(project_name)
                
                # Add new vectors
                vectors_added = vector_manager.add_project_vectors(project_name, chunks)
                
                logger.info(f"[API] Indexed {vectors_added} vectors for {project_name}")
            
            return ProjectUploadResponse(
                success=True,
                project_name=project_name,
                files_uploaded=uploaded_count,
                message=f"Successfully uploaded {uploaded_count} files to '{project_name}'"
            )
        
        except Exception as e:
            logger.error(f"[API] Error uploading project: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ========================================================================
    # ENDPOINT: Exit project mode
    # ========================================================================
    
    @router.post("/exit", response_model=ProjectExitResponse)
    async def exit_project_mode(session_id: str):
        """
        Exit project mode and return to normal chat.
        
        Args:
            session_id: Session to exit project mode for
        
        Returns:
            Confirmation
        """
        try:
            if session_manager:
                session_manager.set_project_mode(session_id, None)
            
            logger.info(f"[API] Exited project mode for session {session_id}")
            
            return ProjectExitResponse(
                success=True,
                message="Exited project mode. Back to normal chat."
            )
        except Exception as e:
            logger.error(f"[API] Error exiting project mode: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ========================================================================
    # ENDPOINT: Get sync status
    # ========================================================================
    
    @router.get("/sync-status/{project_name}", response_model=Optional[SyncStatusResponse])
    async def get_sync_status(project_name: str):
        """
        Get last sync status for a project.
        
        Args:
            project_name: Project to check
        
        Returns:
            Last sync log entry
        """
        try:
            log_entry = update_logger.get_project_log(project_name)
            
            if not log_entry:
                return None
            
            return SyncStatusResponse(**log_entry)
        except Exception as e:
            logger.error(f"[API] Error getting sync status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ========================================================================
    # ENDPOINT: Force sync (admin)
    # ========================================================================
    
    @router.post("/sync")
    async def force_sync(project_name: Optional[str] = None):
        """
        Manually trigger sync for a project (or all projects).
        
        Args:
            project_name: Optional project to sync, or all if not provided
        
        Returns:
            Sync result
        """
        try:
            from project_sync_scheduler import get_scheduler
            
            scheduler = get_scheduler()
            if not scheduler:
                raise HTTPException(status_code=500, detail="Scheduler not initialized")
            
            success = scheduler.force_sync(project_name)
            
            if success:
                message = f"Synced {project_name or 'all projects'}"
                logger.info(f"[API] {message}")
                return {"success": True, "message": message}
            else:
                return {"success": False, "message": "Sync failed"}
        
        except Exception as e:
            logger.error(f"[API] Error forcing sync: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router


# ============================================================================
# HELPER FUNCTIONS FOR INTEGRATION
# ============================================================================

def inject_project_dependencies(app, dependencies: Dict):
    """
    Inject project router into FastAPI app.
    
    Usage:
        router = create_project_router(dependencies)
        inject_project_dependencies(app, dependencies)
    """
    router = create_project_router(dependencies)
    app.include_router(router)
    logger.info("[API] Project router injected")
