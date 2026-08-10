"""
Project System Integration
Connects project module to main pipeline and API
"""

import logging
from typing import Optional, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# SESSION STATE MANAGEMENT FOR PROJECTS
# ============================================================================

class SessionProjectState:
    """
    Manages project mode state for each session.
    Stores whether a session is in project mode and which project.
    """
    
    def __init__(self):
        self.session_states: Dict[str, Optional[str]] = {}  # session_id -> project_name
    
    def get_project(self, session_id: str) -> Optional[str]:
        """Get selected project for session (None if not in project mode)"""
        return self.session_states.get(session_id)
    
    def set_project(self, session_id: str, project_name: Optional[str]) -> None:
        """Set project for session (None to exit project mode)"""
        if project_name is None:
            self.session_states.pop(session_id, None)
            logger.info(f"[SESSION_PROJECT] Exited project mode for {session_id}")
        else:
            self.session_states[session_id] = project_name
            logger.info(f"[SESSION_PROJECT] Set project '{project_name}' for {session_id}")
    
    def is_in_project_mode(self, session_id: str) -> bool:
        """Check if session is in project mode"""
        return session_id in self.session_states and self.session_states[session_id] is not None


# ============================================================================
# RETRIEVAL FILTER FOR PROJECT MODE
# ============================================================================

class ProjectModeRetriever:
    """
    Wrapper around SemanticRetriever that applies project filtering.
    
    When in project mode:
    - Only returns documents with matching project_name
    - Excludes non-project documents
    
    When not in project mode:
    - Excludes all project documents
    - Returns normal SOP/policy documents
    """
    
    def __init__(self, semantic_retriever, project_manager):
        self.retriever = semantic_retriever
        self.project_manager = project_manager
    
    def retrieve(self, query: str, top_k: int = 5, 
                 project_name: Optional[str] = None,
                 video_id: Optional[str] = None) -> list:
        """
        Retrieve documents with optional project filtering.
        
        Args:
            query: User query
            top_k: Number of results
            project_name: If provided, only return docs from this project
            video_id: Video filter (for backward compatibility)
        
        Returns:
            List of (similarity_score, metadata) tuples
        """
        
        # Get all results
        all_results = self.retriever.retrieve(query, top_k=top_k*2, video_id=video_id)
        
        if not all_results:
            return []
        
        # Apply project filtering
        if project_name:
            # In project mode: only return matching project
            results = [
                (score, meta) for score, meta in all_results
                if (meta.get("source_type") == "project_update" and
                    meta.get("project_name") == project_name)
            ]
            logger.debug(f"[RETRIEVAL] Filtered {len(all_results)} -> {len(results)} for project '{project_name}'")
        
        else:
            # Not in project mode: exclude all project data
            results = [
                (score, meta) for score, meta in all_results
                if meta.get("source_type") != "project_update"
            ]
            logger.debug(f"[RETRIEVAL] Filtered {len(all_results)} -> {len(results)} (excluding projects)")
        
        # Return top-k after filtering
        return results[:top_k]


# ============================================================================
# INTEGRATED PIPELINE WITH PROJECT SUPPORT
# ============================================================================

class ProjectAwareGuardedPipeline:
    """
    Wraps GuardedRetrievalPipeline to add project mode support.
    
    Responsibilities:
    - Detect project-related queries
    - Switch to project mode when needed
    - Apply project-specific filtering
    - Route responses appropriately
    """
    
    def __init__(self, 
                 guarded_pipeline,
                 project_query_router,
                 project_aware_retriever,
                 project_manager,
                 session_project_state: SessionProjectState):
        
        self.pipeline = guarded_pipeline
        self.query_router = project_query_router
        self.retriever = project_aware_retriever
        self.project_manager = project_manager
        self.session_state = session_project_state
    
    def process(self, query: str, user_id: str = "default", 
                session_id: Optional[str] = None,
                video_id: Optional[str] = None) -> dict:
        """
        Process query with optional project mode handling.
        
        Flow:
        1. Check if in project mode
        2. If yes and query is for project list → show projects
        3. If yes and query is for exit → exit project mode
        4. If yes and query is normal → answer from project context
        5. If no and query is project-related → enter project mode
        6. Otherwise → normal compliance pipeline
        """
        
        logger.info(f"[PIPELINE] Processing query (session: {session_id})")
        
        # Get current session state
        current_project = self.session_state.get_project(session_id) if session_id else None
        in_project_mode = current_project is not None
        
        logger.debug(f"[PIPELINE] Session state: in_project_mode={in_project_mode}, project={current_project}")
        
        # ====================================================================
        # CASE 1: User wants to exit project mode
        # ====================================================================
        
        if in_project_mode and self.query_router.should_exit_project_mode(query):
            logger.info("[PIPELINE] User requested to exit project mode")
            
            if session_id:
                self.session_state.set_project(session_id, None)
            
            return {
                "success": True,
                "message": "Exited project mode. Back to normal chat.",
                "compliance_allowed": True,
                "project_mode": False,
                "answer": "Exited project mode. You can now ask general compliance and SOP questions."
            }
        
        # ====================================================================
        # CASE 2: User wants to see list of projects
        # ====================================================================
        
        if self.query_router.should_show_projects(query):
            logger.info("[PIPELINE] User requested project list")
            
            from project_query_router import ProjectResponseFormatter
            projects = self.project_manager.list_projects()
            
            return {
                "success": True,
                "message": "Project list retrieved",
                "compliance_allowed": True,
                "project_mode": True,
                "projects": projects,
                "answer": ProjectResponseFormatter.format_project_list(projects)
            }
        
        # ====================================================================
        # CASE 3: User is in project mode - answer from project context
        # ====================================================================
        
        if in_project_mode:
            logger.info(f"[PIPELINE] Processing query in project mode for '{current_project}'")
            
            # Use project-aware retriever
            result = self._process_project_query(query, current_project, session_id)
            return result
        
        # ====================================================================
        # CASE 4: User query is project-related - auto-enter project mode
        # ====================================================================
        
        from project_query_router import QueryType
        query_type = self.query_router.classify_query(query)
        
        if query_type == QueryType.PROJECT:
            logger.info("[PIPELINE] Query classified as PROJECT - entering project mode")
            
            # Try to extract project name
            extracted_project = self.query_router.extract_project_name(query)
            
            if extracted_project:
                # Check if project exists
                available_projects = self.project_manager.list_projects()
                
                # Try exact match
                matching_project = None
                for proj in available_projects:
                    if proj.lower() == extracted_project.lower():
                        matching_project = proj
                        break
                
                # Try partial match
                if not matching_project:
                    for proj in available_projects:
                        if extracted_project.lower() in proj.lower():
                            matching_project = proj
                            break
                
                if matching_project:
                    logger.info(f"[PIPELINE] Auto-entering project mode for '{matching_project}'")
                    
                    if session_id:
                        self.session_state.set_project(session_id, matching_project)
                    
                    result = self._process_project_query(query, matching_project, session_id)
                    return result
            
            # If no specific project found, show list
            from project_query_router import ProjectResponseFormatter
            projects = self.project_manager.list_projects()
            
            if projects:
                logger.info("[PIPELINE] No specific project extracted - showing list")
                
                return {
                    "success": True,
                    "message": "Which project would you like to know about?",
                    "compliance_allowed": True,
                    "project_mode": True,
                    "projects": projects,
                    "answer": ProjectResponseFormatter.format_project_list(projects)
                }
            else:
                logger.info("[PIPELINE] No projects available")
                
                return {
                    "success": False,
                    "message": "No projects available. Please upload project data first.",
                    "compliance_allowed": True,
                    "project_mode": False,
                    "answer": "No projects are available yet. Please ask a compliance or SOP question instead."
                }
        
        # ====================================================================
        # CASE 5: Normal compliance/SOP query - use main pipeline
        # ====================================================================
        
        logger.info("[PIPELINE] Processing normal compliance query")
        
        result = self.pipeline.process(query, user_id=user_id, video_id=video_id)
        
        # Add project mode flag
        result["project_mode"] = False
        
        return result
    
    def _process_project_query(self, query: str, project_name: str, 
                               session_id: Optional[str] = None) -> dict:
        """
        Process a query in project mode.
        
        Uses project-specific vector search and LLM.
        """
        
        try:
            # Retrieve project-specific documents
            from project_query_router import ProjectResponseFormatter
            
            documents = self.retriever.retrieve(query, top_k=5, project_name=project_name)
            
            if not documents:
                logger.warning(f"[PIPELINE] No documents found for project '{project_name}'")
                
                return {
                    "success": False,
                    "message": f"No information found in {project_name}",
                    "compliance_allowed": True,
                    "project_mode": True,
                    "selected_project": project_name,
                    "answer": f"I couldn't find relevant information about that in the {project_name} project."
                }
            
            # Get project metadata
            update_log = None
            if hasattr(self.project_manager, 'get_project_log'):
                update_log = self.project_manager.get_project_log(project_name)
            
            last_updated = update_log.get('last_sync', 'Unknown') if update_log else 'Unknown'
            
            # Build context from documents
            doc_contexts = []
            source_files = set()
            
            for similarity, metadata in documents:
                doc_contexts.append(metadata.get('content', ''))
                source_files.add(metadata.get('source_file', 'Unknown'))
            
            context = "\n\n".join(doc_contexts)
            
            # Call LLM with project context
            system_prompt = f"""You are answering questions about the {project_name} project.
Use ONLY the provided project information.
Be specific and cite sources.
If information is not available, say so clearly."""
            
            llm_response = self.pipeline.llm_controller.generate(
                prompt=query,
                context=context,
                system_prompt=system_prompt
            )
            
            # Format response
            answer = ProjectResponseFormatter.format_project_answer(
                project_name=project_name,
                last_updated=last_updated,
                llm_answer=llm_response,
                source_files=list(source_files)
            )
            
            return {
                "success": True,
                "message": f"Project update from {project_name}",
                "compliance_allowed": True,
                "project_mode": True,
                "selected_project": project_name,
                "answer": answer,
                "retrieved_documents": [
                    {
                        "similarity": score,
                        "metadata": meta,
                        "content_preview": meta.get('content', '')[:200]
                    }
                    for score, meta in documents
                ]
            }
        
        except Exception as e:
            logger.error(f"[PIPELINE] Error processing project query: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": f"Error processing project query: {str(e)}",
                "compliance_allowed": False,
                "project_mode": True,
                "selected_project": project_name,
                "answer": f"An error occurred while processing your query: {str(e)}"
            }


# ============================================================================
# INITIALIZATION HELPER
# ============================================================================

def integrate_project_system(guarded_pipeline, 
                            semantic_retriever,
                            project_manager=None,
                            update_logger=None,
                            vector_manager=None,
                            embedding_model=None,
                            ingestion_pipeline=None) -> Tuple[ProjectAwareGuardedPipeline, SessionProjectState]:
    """
    Integrate project system with existing pipeline.
    
    Args:
        guarded_pipeline: Existing GuardedRetrievalPipeline
        semantic_retriever: Existing SemanticRetriever
        Other parameters for project module initialization
    
    Returns:
        (ProjectAwareGuardedPipeline, SessionProjectState)
    """
    
    logger.info("[INTEGRATION] Starting project system integration...")
    
    # Initialize project module if needed
    if project_manager is None:
        from project_updates import ProjectManager
        from notion_integration import initialize_notion_integration
        
        project_manager = ProjectManager()
        
        # Initialize Notion integration (auto-loads from extracted dataset)
        notion_loader = initialize_notion_integration(project_manager)
        logger.info("[INTEGRATION] ✓ Notion integration initialized")
    
    if update_logger is None:
        from project_updates import UpdateLogger
        update_logger = UpdateLogger()
    
    # Create session state manager
    session_state = SessionProjectState()
    logger.info("[INTEGRATION] ✓ Session project state initialized")
    
    # Create project-aware retriever
    project_aware_retriever = ProjectModeRetriever(semantic_retriever, project_manager)
    logger.info("[INTEGRATION] ✓ Project-aware retriever created")
    
    # Create query router
    from project_query_router import ProjectQueryRouter
    query_router = ProjectQueryRouter()
    logger.info("[INTEGRATION] ✓ Project query router created")
    
    # Create integrated pipeline
    integrated_pipeline = ProjectAwareGuardedPipeline(
        guarded_pipeline,
        query_router,
        project_aware_retriever,
        project_manager,
        session_state
    )
    logger.info("[INTEGRATION] ✓ Integrated pipeline created")
    
    # Initialize scheduler if vector manager available
    if vector_manager and ingestion_pipeline:
        try:
            from project_sync_scheduler import initialize_scheduler, start_scheduler
            
            scheduler = initialize_scheduler(
                project_manager,
                vector_manager,
                ingestion_pipeline,
                update_logger,
                interval_seconds=6 * 3600  # 6 hours
            )
            
            scheduler.start()
            logger.info("[INTEGRATION] ✓ Background scheduler started")
        except Exception as e:
            logger.warning(f"[INTEGRATION] Could not start scheduler: {e}")
    
    logger.info("[INTEGRATION] Project system integration complete!")
    
    return integrated_pipeline, session_state
