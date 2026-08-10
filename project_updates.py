"""
Project Updates Module - Notion Integration
Separate microservice for project retrieval and management
Integrates with Notion workspace extraction
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

PROJECT_BASE_DIR = Path("data/project_updates")
PROJECT_NOTION_DIR = PROJECT_BASE_DIR / "notion"  # Notion exports folder
PROJECT_RAW_EXPORTS = PROJECT_NOTION_DIR  # Use notion folder for raw exports
PROJECT_PROCESSED = PROJECT_BASE_DIR / "processed"
PROJECT_LOGS = PROJECT_BASE_DIR / "logs"
UPDATE_LOG_FILE = PROJECT_LOGS / "update_log.json"

# Ensure directories exist
for directory in [PROJECT_NOTION_DIR, PROJECT_PROCESSED, PROJECT_LOGS]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ProjectMetadata:
    """Metadata for a project in the vector store"""
    source_type: str = "project_update"  # Always "project_update"
    project_name: str = ""
    last_updated: str = ""
    source_file: str = ""
    chunk_id: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict) -> 'ProjectMetadata':
        return ProjectMetadata(**d)


@dataclass
class UpdateLog:
    """Record of a project update sync"""
    project_name: str
    files_processed: int
    vectors_indexed: int
    last_sync: str
    status: str = "success"
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================================
# PROJECT MANAGER - Core Storage Logic
# ============================================================================

class ProjectManager:
    """
    Manages project storage and lifecycle.
    
    Responsibilities:
    - Create/update project folders
    - List available projects
    - Get project content
    - Handle project naming & deduplication
    """
    
    def __init__(self, base_path: Path = PROJECT_RAW_EXPORTS):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"[PROJECT] ProjectManager initialized at {base_path}")
    
    def list_projects(self) -> List[str]:
        """Get all project names"""
        if not self.base_path.exists():
            return []
        
        projects = [d.name for d in self.base_path.iterdir() if d.is_dir()]
        logger.info(f"[PROJECT] Found {len(projects)} projects: {projects}")
        return sorted(projects)
    
    def project_exists(self, project_name: str) -> bool:
        """Check if project folder exists"""
        return (self.base_path / project_name).exists()
    
    def get_project_path(self, project_name: str) -> Path:
        """Get project directory path"""
        return self.base_path / project_name
    
    def create_or_get_project(self, project_name: str) -> Path:
        """Create project folder if doesn't exist, return path"""
        project_path = self.get_project_path(project_name)
        project_path.mkdir(parents=True, exist_ok=True)
        
        if not self.project_exists(project_name):
            logger.info(f"[PROJECT] Created new project: {project_name}")
        
        return project_path
    
    def save_project_file(self, project_name: str, filename: str, content: str) -> bool:
        """Save file to project folder (overwrites if exists)"""
        try:
            project_path = self.create_or_get_project(project_name)
            file_path = project_path / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"[PROJECT] Saved {filename} to {project_name}")
            return True
        except Exception as e:
            logger.error(f"[PROJECT] Error saving {filename}: {e}")
            return False
    
    def get_project_files(self, project_name: str) -> List[Path]:
        """Get all files in project folder"""
        project_path = self.get_project_path(project_name)
        
        if not project_path.exists():
            return []
        
        files = list(project_path.glob("**/*.md")) + list(project_path.glob("**/*.txt"))
        logger.info(f"[PROJECT] Found {len(files)} files in {project_name}")
        return files
    
    def get_project_content(self, project_name: str) -> Dict[str, str]:
        """Get all files and their content from a project"""
        content = {}
        files = self.get_project_files(project_name)
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content[file_path.name] = f.read()
            except Exception as e:
                logger.error(f"[PROJECT] Error reading {file_path}: {e}")
        
        return content
    
    def clear_project(self, project_name: str) -> bool:
        """Clear project files (for updates)"""
        try:
            import shutil
            project_path = self.get_project_path(project_name)
            
            if project_path.exists():
                # Remove all content but keep folder
                for item in project_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
            
            logger.info(f"[PROJECT] Cleared project: {project_name}")
            return True
        except Exception as e:
            logger.error(f"[PROJECT] Error clearing {project_name}: {e}")
            return False


# ============================================================================
# UPDATE LOGGER
# ============================================================================

class UpdateLogger:
    """Manage project update logs"""
    
    def __init__(self, log_file: Path = UPDATE_LOG_FILE):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def add_entry(self, entry: UpdateLog) -> bool:
        """Add update log entry"""
        try:
            logs = self._read_logs()
            logs.append(entry.to_dict())
            
            with open(self.log_file, 'w') as f:
                json.dump(logs, f, indent=2)
            
            logger.info(f"[UPDATE_LOG] Logged update for {entry.project_name}")
            return True
        except Exception as e:
            logger.error(f"[UPDATE_LOG] Error logging: {e}")
            return False
    
    def get_project_log(self, project_name: str) -> Optional[Dict]:
        """Get latest log entry for project"""
        try:
            logs = self._read_logs()
            matching = [l for l in logs if l.get('project_name') == project_name]
            return matching[-1] if matching else None
        except Exception as e:
            logger.error(f"[UPDATE_LOG] Error reading: {e}")
            return None
    
    def _read_logs(self) -> List[Dict]:
        """Read all logs"""
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, 'r') as f:
                return json.load(f)
        except:
            return []


# ============================================================================
# PROJECT INGESTION - Prepare for Vector Indexing
# ============================================================================

class ProjectIngestionPipeline:
    """
    Process project files for vector indexing.
    
    Responsibilities:
    - Chunk project content (~800 tokens)
    - Add project metadata
    - Prepare for embedding
    """
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.project_manager = ProjectManager()
    
    def ingest_project(self, project_name: str) -> List[Dict]:
        """
        Ingest a project and return chunks with metadata.
        
        Returns:
            List of chunks with metadata
        """
        logger.info(f"[INGESTION] Ingesting project: {project_name}")
        
        chunks = []
        content_map = self.project_manager.get_project_content(project_name)
        last_updated = datetime.utcnow().isoformat()
        
        for filename, content in content_map.items():
            if not content.strip():
                continue
            
            # Split into chunks
            file_chunks = self._chunk_content(content, filename, project_name, last_updated)
            chunks.extend(file_chunks)
        
        logger.info(f"[INGESTION] Created {len(chunks)} chunks from {project_name}")
        return chunks
    
    def _chunk_content(self, content: str, filename: str, project_name: str, last_updated: str) -> List[Dict]:
        """Split content into chunks with metadata"""
        chunks = []
        words = content.split()
        
        current_chunk = []
        current_size = 0
        chunk_id = 0
        
        for word in words:
            current_chunk.append(word)
            current_size += len(word.split())
            
            if current_size >= self.chunk_size:
                chunk_text = ' '.join(current_chunk)
                metadata = ProjectMetadata(
                    source_type="project_update",
                    project_name=project_name,
                    last_updated=last_updated,
                    source_file=filename,
                    chunk_id=f"{project_name}_{filename}_{chunk_id}"
                )
                
                chunks.append({
                    "content": chunk_text,
                    "metadata": metadata.to_dict()
                })
                
                # Overlap for context
                overlap_count = int(self.chunk_overlap / 10)  # Approximate overlap
                current_chunk = current_chunk[-overlap_count:] if overlap_count > 0 else []
                current_size = len(current_chunk)
                chunk_id += 1
        
        # Handle remaining content
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            metadata = ProjectMetadata(
                source_type="project_update",
                project_name=project_name,
                last_updated=last_updated,
                source_file=filename,
                chunk_id=f"{project_name}_{filename}_{chunk_id}"
            )
            
            chunks.append({
                "content": chunk_text,
                "metadata": metadata.to_dict()
            })
        
        return chunks


# ============================================================================
# PROJECT VECTOR MANAGER - Manage Vector Store Updates
# ============================================================================

class ProjectVectorManager:
    """
    Manage project-specific vector operations.
    
    Responsibilities:
    - Add project vectors to FAISS
    - Remove project vectors (on update)
    - Filter retrieval by project
    """
    
    def __init__(self, vector_store, embedding_model):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
    
    def remove_project_vectors(self, project_name: str) -> int:
        """
        Remove all vectors for a project from FAISS.
        
        Returns:
            Count of removed vectors
        """
        logger.info(f"[VECTOR] Removing vectors for project: {project_name}")
        
        removed = 0
        # Track indices to remove
        indices_to_remove = []
        
        for idx, metadata in enumerate(self.vector_store.metadata):
            if (metadata.get("source_type") == "project_update" and 
                metadata.get("project_name") == project_name):
                indices_to_remove.append(idx)
                removed += 1
        
        # Remove in reverse order to maintain indices
        for idx in sorted(indices_to_remove, reverse=True):
            self.vector_store.metadata.pop(idx)
        
        logger.info(f"[VECTOR] Removed {removed} vectors for {project_name}")
        return removed
    
    def add_project_vectors(self, project_name: str, chunks: List[Dict]) -> int:
        """
        Add project vectors to FAISS.
        
        Returns:
            Count of added vectors
        """
        logger.info(f"[VECTOR] Adding vectors for project: {project_name}")
        
        if not chunks:
            return 0
        
        # Embed all chunks
        contents = [chunk["content"] for chunk in chunks]
        embeddings = self.embedding_model.embed_texts(contents)
        
        # Prepare metadata
        metadata_list = [chunk["metadata"] for chunk in chunks]
        
        # Add to vector store
        import numpy as np
        embeddings_array = np.array(embeddings, dtype='float32')
        self.vector_store.add_embeddings(embeddings_array, metadata_list)
        
        logger.info(f"[VECTOR] Added {len(chunks)} vectors for {project_name}")
        return len(chunks)
    
    def get_project_vectors(self, project_name: str) -> int:
        """Count vectors for a project"""
        count = sum(
            1 for meta in self.vector_store.metadata
            if (meta.get("source_type") == "project_update" and
                meta.get("project_name") == project_name)
        )
        return count


# ============================================================================
# MOCK NOTION EXTRACTOR (for testing)
# ============================================================================

class NotionExtractor:
    """
    Extract project data from Notion workspace.
    
    Uses the official Notion API to extract databases, pages, and files.
    Converts them into project structure for the knowledge base.
    """
    
    def __init__(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        self.notion_dir = PROJECT_NOTION_DIR
    
    def extract_from_notion(self, api_key: str) -> bool:
        """
        Extract project data from Notion workspace using the Notion extractor tool.
        
        Args:
            api_key: Notion API key (starts with 'ntn_' or 'secret_')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            import sys
            import json
            from pathlib import Path
            from datetime import datetime
            
            # Import the notion extractor from Notion folder
            sys.path.insert(0, str(Path(__file__).parent / "Notion"))
            from notion_extractor import NotionExtractor as NotionAPI
            
            logger.info("[NOTION] Starting Notion workspace extraction...")
            
            # Initialize the extractor
            extractor = NotionAPI(api_key=api_key, output_dir=str(self.notion_dir / "extraction"))
            extractor.setup_directories()
            
            # Search for all accessible content
            items = extractor.search_all()
            
            if not items:
                logger.warning("[NOTION] No items found in Notion workspace")
                return False
            
            # Extract databases
            logger.info("[NOTION] Extracting databases...")
            for item in items:
                if item.get("object") == "database":
                    self._extract_database(extractor, item)
            
            # Extract pages
            logger.info("[NOTION] Extracting pages...")
            for item in items:
                if item.get("object") == "page":
                    self._extract_page(extractor, item)
            
            logger.info(f"[NOTION] ✓ Extraction complete")
            logger.info(f"[NOTION]   Databases: {extractor.stats['databases_exported']}")
            logger.info(f"[NOTION]   Pages: {extractor.stats['pages_exported']}")
            logger.info(f"[NOTION]   Files: {extractor.stats['files_created']}")
            
            return True
            
        except ImportError as e:
            logger.warning(f"[NOTION] Notion API extractor not available: {e}")
            logger.info("[NOTION] Using extracted dataset from Notion/final_extracted_dataset instead")
            return self._load_from_extracted_dataset()
        except Exception as e:
            logger.error(f"[NOTION] Extraction error: {e}", exc_info=True)
            return False
    
    def _extract_database(self, extractor, database_item: Dict) -> bool:
        """Extract a single database and create project from it"""
        try:
            database_id = database_item["id"]
            db_data = extractor.get_database(database_id)
            
            if not db_data:
                return False
            
            # Get database title
            db_title = db_data.get("title", [])
            db_name = extractor.extract_text_from_rich_text(db_title) or database_id
            
            logger.info(f"[NOTION] Exporting database: {db_name}")
            
            # Query all rows
            rows = extractor.query_database(database_id)
            
            # Convert to CSV format
            csv_content = extractor.export_database_to_csv(database_id, rows)
            
            # Save as project
            self.project_manager.save_project_file(db_name, "data.csv", csv_content)
            extractor.stats["databases_exported"] += 1
            
            return True
        except Exception as e:
            logger.error(f"[NOTION] Error extracting database: {e}")
            return False
    
    def _extract_page(self, extractor, page_item: Dict) -> bool:
        """Extract a single page and create project from it"""
        try:
            page_id = page_item["id"]
            page_data = extractor.get_page(page_id)
            
            if not page_data:
                return False
            
            # Get page title
            page_title = extractor.get_page_title(page_data)
            
            logger.info(f"[NOTION] Exporting page: {page_title}")
            
            # Get page content (blocks)
            blocks = extractor.get_blocks(page_id)
            
            # Convert to Markdown
            markdown_content = ""
            for block in blocks:
                markdown_content += extractor.block_to_markdown(block)
            
            # Save as project
            self.project_manager.save_project_file(page_title, "content.md", markdown_content)
            extractor.stats["pages_exported"] += 1
            
            return True
        except Exception as e:
            logger.error(f"[NOTION] Error extracting page: {e}")
            return False
    
    def _load_from_extracted_dataset(self) -> bool:
        """
        Load from pre-extracted Notion dataset.
        Fallback when Notion API is not available.
        """
        try:
            extracted_dir = Path(__file__).parent / "Notion" / "final_extracted_dataset"
            
            if not extracted_dir.exists():
                logger.warning(f"[NOTION] Extracted dataset not found at {extracted_dir}")
                return False
            
            logger.info(f"[NOTION] Loading from pre-extracted dataset: {extracted_dir}")
            
            # Load pages (Markdown)
            pages_dir = extracted_dir / "pages"
            if pages_dir.exists():
                for md_file in pages_dir.glob("*.md"):
                    project_name = md_file.stem
                    content = md_file.read_text(encoding='utf-8')
                    self.project_manager.save_project_file(project_name, md_file.name, content)
                    logger.info(f"[NOTION] ✓ Loaded page: {project_name}")
            
            # Load databases (CSV)
            databases_dir = extracted_dir / "databases"
            if databases_dir.exists():
                for csv_file in databases_dir.glob("*.csv"):
                    project_name = csv_file.stem
                    content = csv_file.read_text(encoding='utf-8')
                    self.project_manager.save_project_file(project_name, csv_file.name, content)
                    logger.info(f"[NOTION] ✓ Loaded database: {project_name}")
            
            logger.info("[NOTION] ✓ Extracted dataset loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"[NOTION] Error loading extracted dataset: {e}", exc_info=True)
            return False
    
    def upload_project_data(self, project_name: str, files: Dict[str, str]) -> bool:
        """
        Manually upload project data (for testing/manual uploads).
        
        Args:
            project_name: Name of project
            files: Dict of {filename: content}
        """
        try:
            for filename, content in files.items():
                self.project_manager.save_project_file(project_name, filename, content)
            
            logger.info(f"[NOTION] Uploaded data to project: {project_name}")
            return True
        except Exception as e:
            logger.error(f"[NOTION] Upload error: {e}")
            return False


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_project_module() -> Dict:
    """Initialize project updates module with Notion integration"""
    logger.info("[PROJECT] Initializing Project Updates Module")
    
    project_manager = ProjectManager()
    update_logger = UpdateLogger()
    ingestion = ProjectIngestionPipeline()
    notion_extractor = NotionExtractor(project_manager)
    
    # Try to auto-load from Notion extracted dataset
    logger.info("[PROJECT] Auto-loading from Notion extracted dataset...")
    if notion_extractor._load_from_extracted_dataset():
        logger.info("[PROJECT] ✓ Notion projects loaded successfully")
    else:
        logger.info("[PROJECT] ℹ️ No Notion projects found (this is optional)")
    
    return {
        "project_manager": project_manager,
        "update_logger": update_logger,
        "ingestion": ingestion,
        "notion_extractor": notion_extractor
    }
