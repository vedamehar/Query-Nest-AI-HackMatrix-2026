"""
Unified Ingestion Pipeline: Single entry point for all document sources.

Handles:
- Internal Data1 files
- Admin uploaded documents
- Future document sources

All documents go through identical pipeline:
Load → Extract → Chunk → Metadata → Embed → Insert → Save
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import sys


@dataclass
class IngestionResult:
    """Result of document ingestion process."""
    
    success: bool = False
    error: Optional[str] = None
    file_type: Optional[str] = None
    folder_type: Optional[str] = None
    text_length: int = 0
    chunk_count: int = 0
    document_id: Optional[str] = None
    version: int = 0
    faiss_indices: Tuple[int, int] = (0, 0)
    total_vectors: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "document_id": self.document_id,
            "version": self.version,
            "file_type": self.file_type,
            "folder_type": self.folder_type,
            "text_length": self.text_length,
            "chunk_count": self.chunk_count,
            "faiss_indices": self.faiss_indices,
            "total_vectors": self.total_vectors,
            "timestamp": self.timestamp
        }


class DocumentDetector:
    """Identifies document type and folder category."""
    
    FOLDER_MAPPING = {
        "Policies": ["policies", "policy"],
        "SOPs": ["sops", "sop", "procedures"],
        "Internal": ["internal", "decisions"],
        "Technical": ["technical", "architecture", "technical"],
    }
    
    @staticmethod
    def detect(file_path: str, source_type: str) -> Dict[str, str]:
        """Detect document properties from path."""
        path = Path(file_path)
        
        # Determine file type
        file_type = path.suffix.lower().lstrip('.')
        if file_type == "md":
            file_type = "markdown"
        elif file_type == "markdown":
            file_type = "markdown"
        
        # Determine folder type from path
        folder_type = "General"
        for category, keywords in DocumentDetector.FOLDER_MAPPING.items():
            if any(kw in str(path).lower() for kw in keywords):
                folder_type = category
                break
        
        return {
            "file_type": file_type,
            "folder_type": folder_type,
            "source_type": source_type
        }


class MetadataBuilder:
    """Builds standardized metadata for chunks."""
    
    @staticmethod
    def generate_document_id(file_path: str, source_type: str) -> str:
        """Generate unique document ID."""
        file_path = str(file_path)
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        file_hash = hashlib.sha256(file_path.encode()).hexdigest()[:8]
        doc_id = f"doc_{timestamp}_{source_type[0]}_{file_hash}"
        return doc_id
    
    @staticmethod
    def build_metadata_for_chunk(
        chunk_text: str,
        chunk_sequence: int,
        document_id: str,
        document_name: str,
        version: int,
        source_type: str,
        folder_type: str,
        file_type: str,
        page_number: Optional[int] = None,
        section_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build standardized metadata for single chunk."""
        
        chunk_id = f"{document_id}_chunk_{chunk_sequence:04d}"
        
        # Token estimation (1 token ≈ 4 chars)
        token_count = len(chunk_text) // 4
        
        metadata = {
            # Identity & Versioning
            "document_id": document_id,
            "document_name": document_name,
            "version": version,
            "active_version": True,
            
            # Source Information
            "source_type": source_type,
            "folder_type": folder_type,
            "file_type": file_type,
            
            # Content Metadata
            "chunk_id": chunk_id,
            "chunk_sequence": chunk_sequence,
            "page_number": page_number,
            "section_title": section_title,
            
            # Timing
            "upload_timestamp": datetime.utcnow().isoformat() + "Z",
            "indexed_timestamp": datetime.utcnow().isoformat() + "Z",
            
            # Quality Metrics
            "text_length": len(chunk_text),
            "token_count": token_count,
            "extraction_confidence": 1.0,
            
            # Traceability
            "content_hash": hashlib.sha256(chunk_text.encode()).hexdigest()[:16],
            "pipeline_version": "2.0",
            "embedding_model": "all-MiniLM-L6-v2",
            
            # Status
            "ingestion_status": "success",
            "retrieval_enabled": True,
            
            # Citation Support
            "display_name": document_name,
            "display_section": section_title or "General",
            
            # The actual content
            "text": chunk_text
        }
        
        return metadata


class SemanticChunker:
    """Chunks text into semantic segments (500-800 tokens)."""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_length = 50
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count (1 token ≈ 4 chars)."""
        return len(text) // 4
    
    def chunk(self, text: str, doc_type: str = "text") -> List[Dict[str, Any]]:
        """Split text into chunks with metadata."""
        
        chunks = []
        
        # For PDF, respect page breaks
        if doc_type == "pdf" and "--- PAGE" in text:
            current_chunk = ""
            current_tokens = 0
            page_num = 1
            
            for line in text.split('\n'):
                if "--- PAGE" in line:
                    if current_chunk.strip():
                        chunks.append({
                            "text": current_chunk.strip(),
                            "page": page_num,
                            "start_token": len(chunks) * self.chunk_size
                        })
                    try:
                        page_num = int(line.split()[-1].rstrip("---"))
                    except ValueError:
                        page_num += 1
                    current_chunk = ""
                    current_tokens = 0
                else:
                    line_tokens = self.estimate_tokens(line)
                    if current_tokens + line_tokens > self.chunk_size and current_chunk:
                        chunks.append({
                            "text": current_chunk.strip(),
                            "page": page_num,
                            "start_token": len(chunks) * self.chunk_size
                        })
                        current_chunk = line
                        current_tokens = line_tokens
                    else:
                        current_chunk += "\n" + line
                        current_tokens += line_tokens
            
            if current_chunk.strip():
                chunks.append({
                    "text": current_chunk.strip(),
                    "page": page_num,
                    "start_token": len(chunks) * self.chunk_size
                })
        else:
            # For text, CSV, Markdown - use word-based chunking
            words = text.split()
            current_chunk = []
            current_tokens = 0
            
            for word in words:
                word_tokens = self.estimate_tokens(word)
                if current_tokens + word_tokens > self.chunk_size and current_chunk:
                    chunk_text = " ".join(current_chunk)
                    if len(chunk_text.strip()) >= self.min_chunk_length:
                        chunks.append({
                            "text": chunk_text.strip(),
                            "page": None,
                            "start_token": len(chunks) * self.chunk_size
                        })
                    # Overlap
                    overlap_words = 20 if self.overlap > 50 else 10
                    current_chunk = current_chunk[-overlap_words:] if len(current_chunk) > overlap_words else current_chunk
                    current_tokens = self.estimate_tokens(" ".join(current_chunk))
                
                current_chunk.append(word)
                current_tokens += word_tokens
            
            # Add final chunk
            if current_chunk:
                chunk_text = " ".join(current_chunk)
                if len(chunk_text.strip()) >= self.min_chunk_length:
                    chunks.append({
                        "text": chunk_text.strip(),
                        "page": None,
                        "start_token": len(chunks) * self.chunk_size
                    })
        
        return chunks


class UnifiedIngestionPipeline:
    """Main orchestrator for all document sources."""
    
    def __init__(self, vector_manager, embedding_model):
        """Initialize pipeline."""
        self.vector_manager = vector_manager
        self.embedding_model = embedding_model
        self.chunker = SemanticChunker()
        self.metadata_builder = MetadataBuilder()
        self.detector = DocumentDetector()
    
    def ingest_document(self, file_path: str, source_type: str = "Admin") -> IngestionResult:
        """
        Unified document ingestion.
        
        Args:
            file_path: Path to document file
            source_type: "Internal" or "Admin"
            
        Returns:
            IngestionResult with success status and metadata
        """
        result = IngestionResult()
        
        try:
            file_path = str(file_path)
            
            # Step 1: Validate file exists
            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            print(f"\n[1/7] Detecting document type...")
            doc_info = self.detector.detect(file_path, source_type)
            result.file_type = doc_info["file_type"]
            result.folder_type = doc_info["folder_type"]
            print(f"  ✓ Type: {result.file_type}, Folder: {result.folder_type}")
            
            # Step 2: Load document
            print(f"\n[2/7] Loading {result.file_type} file...")
            try:
                from loaders.loader_registry import LoaderRegistry
                loader = LoaderRegistry.get_loader(file_path)
                text = loader.load(file_path)
            except ImportError:
                print("  ⚠ LoaderRegistry not available, using basic loading")
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            
            result.text_length = len(text)
            if not text.strip():
                raise ValueError("Text extraction returned empty")
            
            print(f"  ✓ Extracted {result.text_length} characters")
            
            # Step 3: Generate document ID
            print(f"\n[3/7] Generating document ID...")
            doc_id = self.metadata_builder.generate_document_id(file_path, source_type)
            version = 1  # Would call vector_manager.get_next_version(doc_id) if implemented
            print(f"  ✓ Doc ID: {doc_id}, Version: {version}")
            
            # Step 4: Chunk text
            print(f"\n[4/7] Chunking text ({result.file_type})...")
            chunks = self.chunker.chunk(text, result.file_type)
            result.chunk_count = len(chunks)
            print(f"  ✓ Created {result.chunk_count} chunks")
            
            # Step 5: Build metadata
            print(f"\n[5/7] Building standardized metadata...")
            metadata_list = []
            doc_name = Path(file_path).name
            
            for idx, chunk_data in enumerate(chunks):
                metadata = self.metadata_builder.build_metadata_for_chunk(
                    chunk_text=chunk_data["text"],
                    chunk_sequence=idx,
                    document_id=doc_id,
                    document_name=doc_name,
                    version=version,
                    source_type=source_type,
                    folder_type=result.folder_type,
                    file_type=result.file_type,
                    page_number=chunk_data.get("page"),
                    section_title=None
                )
                metadata_list.append(metadata)
            
            print(f"  ✓ {len(metadata_list)} metadata records created")
            
            # Step 6: Generate embeddings
            print(f"\n[6/7] Generating embeddings...")
            texts = [m["text"] for m in metadata_list]
            embeddings = self.embedding_model.embed_texts(texts)
            print(f"  ✓ {len(embeddings)} embeddings generated")
            
            # Step 7: Insert into vector store
            print(f"\n[7/7] Inserting into vector store...")
            insert_result = self.vector_manager.insert_with_validation(
                embeddings, metadata_list
            )
            
            result.success = True
            result.document_id = doc_id
            result.version = version
            result.faiss_indices = insert_result.get("faiss_indices", (0, 0))
            result.total_vectors = insert_result.get("new_total", 0)
            
            print(f"\n✓ Document ingested successfully!")
            print(f"  Document ID: {doc_id} (v{version})")
            print(f"  Chunks: {result.chunk_count}")
            print(f"  Index size: {result.total_vectors} vectors")
            
            return result
        
        except Exception as e:
            result.success = False
            result.error = str(e)
            print(f"\n✗ Ingestion failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return result


# Simple standalone test
if __name__ == "__main__":
    print("Unified Ingestion Pipeline - Module Check")
    print("=" * 70)
    print("✓ DocumentDetector available")
    print("✓ SemanticChunker available")
    print("✓ MetadataBuilder available")
    print("✓ UnifiedIngestionPipeline available")
    print("✓ IngestionResult available")
