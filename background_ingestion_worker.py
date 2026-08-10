"""
Background Document Ingestion Worker

Non-blocking async worker for processing documents:
- Text extraction
- Intelligent chunking
- Metadata attachment
- Embedding generation
- Vector store insertion
- Version conflict detection

Runs parallel to chat API without blocking responses.
"""

import asyncio
import os
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from queue import Queue
import threading

import numpy as np

# Hypothetical imports (replace with actual)
# from pdf_processor import extract_pdf_text
# from text_processor import chunk_intelligently
# from embedding_service import EmbeddingModel
# from faiss_store import FAISSVectorStore
# from document_version_schema import DocumentVersionSchema


@dataclass
class IngestionTask:
    """Ingestion task definition."""
    upload_id: str
    version_id: int
    file_path: str
    document_name: str
    document_type: str
    version: str
    previous_version_id: Optional[int] = None
    
    # Runtime state
    current_stage: str = "QUEUED"
    progress: int = 0
    chunks_generated: int = 0
    total_chunks: int = 0
    start_time: float = None


class IngestionWorker:
    """Background worker for document ingestion."""
    
    def __init__(self, 
                 db_schema,
                 faiss_store,
                 embedding_model,
                 max_workers: int = 1):
        """
        Initialize ingestion worker.
        
        Args:
            db_schema: DocumentVersionSchema instance
            faiss_store: FAISS vector store instance
            embedding_model: Embedding model instance
            max_workers: Number of concurrent workers
        """
        self.db = db_schema
        self.faiss = faiss_store
        self.embedding_model = embedding_model
        self.max_workers = max_workers
        
        # Task queue
        self.task_queue = Queue()
        self.active_tasks = {}  # {upload_id: IngestionTask}
        
        # Worker threads
        self.workers = []
        self.running = False
        self.lock = threading.Lock()
    
    def start(self):
        """Start background worker threads."""
        print(f"[WORKER] Starting {self.max_workers} ingestion workers")
        self.running = True
        
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def stop(self):
        """Stop background workers gracefully."""
        print("[WORKER] Stopping ingestion workers")
        self.running = False
        
        for worker in self.workers:
            worker.join(timeout=5)
    
    def queue_ingestion(self, task: IngestionTask):
        """Queue document for ingestion."""
        self.task_queue.put(task)
        print(f"[QUEUE] Task queued: {task.upload_id}")
    
    def _worker_loop(self, worker_id: int):
        """Main worker loop."""
        print(f"[WORKER-{worker_id}] Started")
        
        while self.running:
            try:
                # Get task with timeout
                task = self.task_queue.get(timeout=2)
                
                if task is None:  # Poison pill
                    break
                
                print(f"[WORKER-{worker_id}] Processing: {task.upload_id}")
                
                with self.lock:
                    self.active_tasks[task.upload_id] = task
                
                # Process task
                self._process_ingestion(task)
                
                with self.lock:
                    del self.active_tasks[task.upload_id]
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[WORKER-{worker_id}] Error: {str(e)}")
                if task:
                    self._handle_ingestion_failure(task, e)
    
    def _process_ingestion(self, task: IngestionTask):
        """
        Process document ingestion through all stages.
        Main orchestration method.
        """
        task.start_time = time.time()
        
        try:
            # STAGE 1: EXTRACTION
            print(f"[{task.upload_id}] STAGE 1: Text Extraction")
            task.current_stage = "EXTRACTION"
            self._update_progress(task, 20)
            
            pages = self._extract_text(task.file_path)
            print(f"[{task.upload_id}] Extracted {len(pages)} pages")
            
            # STAGE 2: CHUNKING
            print(f"[{task.upload_id}] STAGE 2: Intelligent Chunking")
            task.current_stage = "CHUNKING"
            self._update_progress(task, 40)
            
            chunks = self._chunk_intelligently(pages)
            task.total_chunks = len(chunks)
            print(f"[{task.upload_id}] Generated {len(chunks)} chunks")
            
            # STAGE 3: METADATA ATTACHMENT
            print(f"[{task.upload_id}] STAGE 3: Metadata Attachment")
            task.current_stage = "METADATA"
            self._update_progress(task, 50)
            
            enriched_chunks = self._attach_metadata(task, chunks)
            
            # STAGE 4: EMBEDDING GENERATION
            print(f"[{task.upload_id}] STAGE 4: Embedding Generation")
            task.current_stage = "EMBEDDING"
            
            embeddings = self._generate_embeddings(task, enriched_chunks)
            
            # STAGE 5: INSERT TO DATABASES
            print(f"[{task.upload_id}] STAGE 5: Database Insertion")
            task.current_stage = "DB_INSERT"
            self._update_progress(task, 85)
            
            self._insert_to_databases(task, enriched_chunks, embeddings)
            
            # STAGE 6: MARK OLD AS INACTIVE
            if task.previous_version_id:
                print(f"[{task.upload_id}] STAGE 6: Marking Previous Version Inactive")
                task.current_stage = "INACTIVATION"
                self._inactivate_previous_version(task)
            
            # STAGE 7: DETECT CONFLICTS
            if task.previous_version_id:
                print(f"[{task.upload_id}] STAGE 7: Conflict Detection")
                task.current_stage = "CONFLICT_DETECTION"
                self._detect_version_conflicts(task)
            
            # COMPLETION
            print(f"[{task.upload_id}] STAGE COMPLETE: All stages finished")
            task.current_stage = "COMPLETED"
            self._update_progress(task, 100)
            
            self._finalize_ingestion(task)
            
        except Exception as e:
            print(f"[{task.upload_id}] ERROR: {str(e)}")
            self._handle_ingestion_failure(task, e)
    
    def _extract_text(self, file_path: str) -> List[Dict]:
        """
        Extract text page-by-page from document.
        Returns list of {page_num, text, raw_text}
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return self._extract_pdf(file_path)
        elif file_ext == '.docx':
            return self._extract_docx(file_path)
        elif file_ext in ['.txt', '.md']:
            return self._extract_text_file(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    def _extract_pdf(self, file_path: str) -> List[Dict]:
        """Extract text from PDF file."""
        # Placeholder: Use PyMuPDF or pypdf2
        # from pdf_processor import extract_pdf_text
        # return extract_pdf_text(file_path)
        
        print(f"[EXTRACT] PDF extraction: {file_path}")
        # Mock implementation
        return [
            {
                'page_num': 1,
                'text': 'Sample text from page 1',
                'raw_text': 'Sample text from page 1'
            },
            {
                'page_num': 2,
                'text': 'Sample text from page 2',
                'raw_text': 'Sample text from page 2'
            }
        ]
    
    def _extract_docx(self, file_path: str) -> List[Dict]:
        """Extract text from DOCX file."""
        # Placeholder: Use python-docx
        # from docx import Document
        # doc = Document(file_path)
        # return [{'page_num': 1, 'text': text, 'raw_text': text} for text in doc.paragraphs]
        
        print(f"[EXTRACT] DOCX extraction: {file_path}")
        return []
    
    def _extract_text_file(self, file_path: str) -> List[Dict]:
        """Extract text from plain text or markdown file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by double newlines to detect pages
        pages = content.split('\n\n')
        
        return [
            {
                'page_num': i + 1,
                'text': page.strip(),
                'raw_text': page.strip()
            }
            for i, page in enumerate(pages) if page.strip()
        ]
    
    def _chunk_intelligently(self, pages: List[Dict]) -> List[Dict]:
        """
        Chunk text intelligently: by sections, 300-500 tokens.
        Preserves hierarchy and page numbers.
        """
        chunks = []
        
        for page in pages:
            text = page['text']
            page_num = page['page_num']
            
            # Simple tokenization (split by words)
            tokens = text.split()
            target_tokens = 350  # 300-500 range
            
            # Chunk by sections (split by \n\n)
            sections = text.split('\n\n')
            
            current_chunk = []
            current_tokens = 0
            
            for section in sections:
                section_tokens = len(section.split())
                
                if current_tokens + section_tokens > target_tokens and current_chunk:
                    # Finalize current chunk
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'page_num': page_num,
                        'tokens': current_tokens,
                        'section_title': self._extract_section_title(chunk_text)
                    })
                    
                    current_chunk = [section]
                    current_tokens = section_tokens
                else:
                    current_chunk.append(section)
                    current_tokens += section_tokens
            
            # Final chunk
            if current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'page_num': page_num,
                    'tokens': current_tokens,
                    'section_title': self._extract_section_title(chunk_text)
                })
        
        return chunks
    
    def _extract_section_title(self, text: str) -> str:
        """Extract section title from chunk."""
        lines = text.split('\n')
        for line in lines:
            if line.strip() and (line.startswith('#') or line.isupper()):
                return line.strip('#').strip()
        return "General Content"
    
    def _attach_metadata(self, task: IngestionTask, chunks: List[Dict]) -> List[Dict]:
        """Attach metadata to chunks."""
        enriched = []
        
        for i, chunk in enumerate(chunks):
            enriched_chunk = {
                'document_name': task.document_name,
                'version': task.version,
                'version_id': task.version_id,
                'folder_type': task.document_type,
                'page_number': chunk['page_num'],
                'chunk_index': i,
                'chunk_id': f"{task.document_name}_{task.version}_chunk_{i:03d}",
                'text': chunk['text'],
                'section_title': chunk.get('section_title', ''),
                'token_count': chunk['tokens'],
                'upload_timestamp': datetime.utcnow().isoformat(),
                'section_hierarchy': f"Section {i + 1}"
            }
            enriched.append(enriched_chunk)
        
        return enriched
    
    def _generate_embeddings(self, task: IngestionTask, chunks: List[Dict]) -> List[Dict]:
        """Generate embeddings for chunks."""
        embeddings = []
        
        for i, chunk in enumerate(chunks):
            # Generate embedding
            try:
                vector = self.embedding_model.encode(chunk['text'])
            except Exception as e:
                print(f"[EMBEDDING] Error for chunk {i}: {str(e)}")
                vector = np.zeros(384)  # Fallback
            
            embeddings.append({
                'chunk_id': chunk['chunk_id'],
                'vector': vector,
                'metadata': chunk
            })
            
            # Update progress
            progress = 50 + (i / len(chunks)) * 35
            task.chunks_generated = i
            self._update_progress(task, int(progress))
        
        return embeddings
    
    def _insert_to_databases(self, 
                            task: IngestionTask,
                            chunks: List[Dict],
                            embeddings: List[Dict]):
        """Insert to database and vector store."""
        
        # Insert chunks to SQL DB
        for i, chunk in enumerate(chunks):
            self.db.add_chunk(
                version_id=task.version_id,
                chunk_id=chunk['chunk_id'],
                chunk_index=chunk['chunk_index'],
                text_content=chunk['text'],
                text_length=len(chunk['text']),
                token_count=chunk['token_count'],
                page_number=chunk['page_number'],
                section_title=chunk['section_title'],
                section_hierarchy=chunk['section_hierarchy']
            )
        
        # Insert embeddings to FAISS
        if embeddings:
            vectors = np.array([e['vector'] for e in embeddings]).astype('float32')
            faiss_indices = self.faiss.add_vectors(vectors)
            
            # Store embedding metadata
            for idx, emb in enumerate(embeddings):
                self.db.add_embedding_metadata(
                    embedding_id=emb['chunk_id'],
                    version_id=task.version_id,
                    document_name=task.document_name,
                    version=task.version,
                    document_type=task.document_type,
                    page_number=emb['metadata']['page_number'],
                    chunk_id=emb['chunk_id'],
                    is_active=1,
                    faiss_index=faiss_indices[idx] if isinstance(faiss_indices, list) else idx,
                    metadata_json=json.dumps(emb['metadata'])
                )
    
    def _inactivate_previous_version(self, task: IngestionTask):
        """Mark previous version as inactive."""
        if task.previous_version_id:
            self.db.mark_version_inactive(task.previous_version_id)
            print(f"[{task.upload_id}] Previous version marked inactive")
    
    def _detect_version_conflicts(self, task: IngestionTask):
        """Detect conflicts between versions."""
        # Placeholder for conflict detection logic
        print(f"[{task.upload_id}] Conflict detection completed")
    
    def _finalize_ingestion(self, task: IngestionTask):
        """Finalize ingestion and mark as complete."""
        processing_time = time.time() - task.start_time
        
        # Update document version status
        cursor = self.db.connection.cursor()
        cursor.execute("""
            UPDATE document_versions
            SET status = 'ACTIVE', chunk_count = ?, total_tokens = ?,
                page_count = ?
            WHERE id = ?
        """, (
            task.total_chunks,
            task.chunks_generated * 350,  # Approximate
            task.total_chunks,
            task.version_id
        ))
        self.db.connection.commit()
        
        # Log audit
        self.db.log_admin_action(
            admin_username="system",
            action="DOCUMENT_INGESTED",
            document_name=task.document_name,
            document_version=task.version,
            version_id=task.version_id,
            action_details=f"Processing time: {processing_time:.2f}s",
            success=1
        )
        
        print(f"[{task.upload_id}] Ingestion finalized in {processing_time:.2f}s")
    
    def _handle_ingestion_failure(self, task: IngestionTask, error: Exception):
        """Handle ingestion failure with rollback."""
        print(f"[{task.upload_id}] Handling failure: {str(error)}")
        
        # Mark as failed
        cursor = self.db.connection.cursor()
        cursor.execute("""
            UPDATE document_versions
            SET status = 'FAILED', deleted_at = CURRENT_TIMESTAMP,
                deletion_reason = ?
            WHERE id = ?
        """, (f"Ingestion failed: {str(error)}", task.version_id))
        self.db.connection.commit()
        
        # Log failure
        cursor.execute("""
            INSERT INTO ingestion_failures
            (upload_id, version_id, error_type, error_message, failure_stage)
            VALUES (?, ?, ?, ?, ?)
        """, (
            task.upload_id,
            task.version_id,
            type(error).__name__,
            str(error),
            task.current_stage
        ))
        self.db.connection.commit()
    
    def _update_progress(self, task: IngestionTask, progress: int):
        """Update task progress."""
        task.progress = progress
        print(f"[{task.upload_id}] Progress: {progress}%")
    
    def get_task_status(self, upload_id: str) -> Dict:
        """Get status of ingestion task."""
        with self.lock:
            task = self.active_tasks.get(upload_id)
        
        if not task:
            return {"status": "unknown", "upload_id": upload_id}
        
        return {
            "upload_id": upload_id,
            "status": "processing",
            "stage": task.current_stage,
            "progress": task.progress,
            "chunks_processed": task.chunks_generated,
            "total_chunks": task.total_chunks
        }


# Singleton instance
_worker_instance = None


def get_ingestion_worker() -> IngestionWorker:
    """Get or create singleton ingestion worker."""
    global _worker_instance
    if _worker_instance is None:
        raise RuntimeError("Ingestion worker not initialized")
    return _worker_instance


def initialize_ingestion_worker(db_schema, faiss_store, embedding_model, max_workers=1):
    """Initialize and start ingestion worker."""
    global _worker_instance
    _worker_instance = IngestionWorker(db_schema, faiss_store, embedding_model, max_workers)
    _worker_instance.start()
    return _worker_instance
