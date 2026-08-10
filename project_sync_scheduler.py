"""
Project Update Scheduler - Background synchronization
Periodically syncs project data from Notion and updates vector store
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# SCHEDULER CONFIGURATION
# ============================================================================

class SchedulerConfig:
    """Configuration for project sync scheduler"""
    
    # How often to check for updates (in seconds)
    DEFAULT_INTERVAL = 6 * 3600  # 6 hours
    
    # Min interval to prevent spam
    MIN_INTERVAL = 300  # 5 minutes
    
    # Max interval to ensure regular checks
    MAX_INTERVAL = 24 * 3600  # 24 hours
    
    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL):
        if interval_seconds < self.MIN_INTERVAL:
            interval_seconds = self.MIN_INTERVAL
        elif interval_seconds > self.MAX_INTERVAL:
            interval_seconds = self.MAX_INTERVAL
        
        self.interval_seconds = interval_seconds
        logger.info(f"[SCHEDULER] Configured with {interval_seconds}s interval")


# ============================================================================
# PROJECT SYNC SCHEDULER
# ============================================================================

class ProjectSyncScheduler:
    """
    Background scheduler for project updates.
    
    Responsibilities:
    - Run sync jobs periodically
    - Handle ingestion and vector updates
    - Log all sync operations
    - Graceful shutdown
    """
    
    def __init__(self, 
                 project_manager,
                 vector_manager,
                 ingestion_pipeline,
                 update_logger,
                 config: SchedulerConfig = None):
        
        self.project_manager = project_manager
        self.vector_manager = vector_manager
        self.ingestion = ingestion_pipeline
        self.update_logger = update_logger
        self.config = config or SchedulerConfig()
        
        # Thread management
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Sync hooks (can be set by app)
        self.on_sync_complete: Optional[Callable] = None
        self.on_sync_error: Optional[Callable] = None
        
        logger.info("[SCHEDULER] Initialized")
    
    def start(self) -> bool:
        """Start the background scheduler"""
        if self.is_running:
            logger.warning("[SCHEDULER] Already running")
            return False
        
        self.is_running = True
        self.stop_event.clear()
        
        # Start scheduler in background thread
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,  # Daemon thread so it doesn't prevent shutdown
            name="ProjectSyncScheduler"
        )
        self.scheduler_thread.start()
        
        logger.info("[SCHEDULER] Started")
        return True
    
    def stop(self) -> bool:
        """Stop the scheduler gracefully"""
        if not self.is_running:
            logger.warning("[SCHEDULER] Not running")
            return False
        
        logger.info("[SCHEDULER] Stopping...")
        self.stop_event.set()
        self.is_running = False
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("[SCHEDULER] Stopped")
        return True
    
    def _scheduler_loop(self):
        """Main scheduler loop (runs in background thread)"""
        logger.info(f"[SCHEDULER] Loop started (interval: {self.config.interval_seconds}s)")
        
        while not self.stop_event.is_set():
            try:
                # Wait for next sync time
                self.stop_event.wait(self.config.interval_seconds)
                
                if self.stop_event.is_set():
                    break
                
                # Run sync
                logger.info("[SCHEDULER] Running sync cycle...")
                self._run_sync_cycle()
                
            except Exception as e:
                logger.error(f"[SCHEDULER] Error in loop: {e}", exc_info=True)
                if self.on_sync_error:
                    try:
                        self.on_sync_error(str(e))
                    except:
                        pass
    
    def _run_sync_cycle(self):
        """Execute one complete sync cycle"""
        from project_updates import UpdateLog
        
        projects = self.project_manager.list_projects()
        
        if not projects:
            logger.info("[SCHEDULER] No projects to sync")
            return
        
        logger.info(f"[SCHEDULER] Syncing {len(projects)} projects")
        
        for project_name in projects:
            try:
                logger.info(f"[SCHEDULER] Syncing project: {project_name}")
                
                # Ingest project
                chunks = self.ingestion.ingest_project(project_name)
                
                if not chunks:
                    logger.warning(f"[SCHEDULER] No chunks for {project_name}")
                    continue
                
                # Remove old vectors
                self.vector_manager.remove_project_vectors(project_name)
                
                # Add new vectors
                vectors_added = self.vector_manager.add_project_vectors(project_name, chunks)
                
                # Log success
                log_entry = UpdateLog(
                    project_name=project_name,
                    files_processed=len(self.project_manager.get_project_files(project_name)),
                    vectors_indexed=vectors_added,
                    last_sync=datetime.utcnow().isoformat(),
                    status="success"
                )
                self.update_logger.add_entry(log_entry)
                
                logger.info(f"[SCHEDULER] ✓ Synced {project_name}: {vectors_added} vectors")
                
            except Exception as e:
                logger.error(f"[SCHEDULER] Error syncing {project_name}: {e}")
                
                # Log error
                log_entry = UpdateLog(
                    project_name=project_name,
                    files_processed=0,
                    vectors_indexed=0,
                    last_sync=datetime.utcnow().isoformat(),
                    status="error",
                    error_message=str(e)
                )
                self.update_logger.add_entry(log_entry)
        
        logger.info("[SCHEDULER] Sync cycle complete")
        
        # Trigger callback
        if self.on_sync_complete:
            try:
                self.on_sync_complete(len(projects))
            except:
                pass
    
    def force_sync(self, project_name: Optional[str] = None) -> bool:
        """
        Manually trigger a sync (don't wait for interval).
        
        Args:
            project_name: Sync specific project, or all if None
        """
        logger.info(f"[SCHEDULER] Force sync triggered (project: {project_name or 'all'})")
        
        try:
            if project_name:
                self._sync_single_project(project_name)
            else:
                self._run_sync_cycle()
            return True
        except Exception as e:
            logger.error(f"[SCHEDULER] Force sync error: {e}")
            if self.on_sync_error:
                try:
                    self.on_sync_error(str(e))
                except:
                    pass
            return False
    
    def _sync_single_project(self, project_name: str):
        """Sync a single project"""
        from project_updates import UpdateLog
        
        chunks = self.ingestion.ingest_project(project_name)
        
        if not chunks:
            logger.warning(f"[SCHEDULER] No chunks for {project_name}")
            return
        
        # Remove old vectors
        self.vector_manager.remove_project_vectors(project_name)
        
        # Add new vectors
        vectors_added = self.vector_manager.add_project_vectors(project_name, chunks)
        
        # Log success
        log_entry = UpdateLog(
            project_name=project_name,
            files_processed=len(self.project_manager.get_project_files(project_name)),
            vectors_indexed=vectors_added,
            last_sync=datetime.utcnow().isoformat(),
            status="success"
        )
        self.update_logger.add_entry(log_entry)
        
        logger.info(f"[SCHEDULER] ✓ Synced {project_name}: {vectors_added} vectors")


# ============================================================================
# GLOBAL SCHEDULER INSTANCE
# ============================================================================

_global_scheduler: Optional[ProjectSyncScheduler] = None


def initialize_scheduler(project_manager, vector_manager, ingestion_pipeline, update_logger,
                        interval_seconds: int = 6 * 3600) -> ProjectSyncScheduler:
    """Initialize global scheduler"""
    global _global_scheduler
    
    config = SchedulerConfig(interval_seconds)
    _global_scheduler = ProjectSyncScheduler(
        project_manager,
        vector_manager,
        ingestion_pipeline,
        update_logger,
        config
    )
    
    return _global_scheduler


def get_scheduler() -> Optional[ProjectSyncScheduler]:
    """Get global scheduler instance"""
    return _global_scheduler


def start_scheduler() -> bool:
    """Start global scheduler"""
    if _global_scheduler:
        return _global_scheduler.start()
    return False


def stop_scheduler() -> bool:
    """Stop global scheduler"""
    if _global_scheduler:
        return _global_scheduler.stop()
    return False
