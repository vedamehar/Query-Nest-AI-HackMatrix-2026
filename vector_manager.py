"""
Vector Manager: Safe FAISS operations with version control and duplicate detection.

Responsibilities:
- Check embedding dimensions
- Prevent duplicate insertions
- Track document versions
- Verify index integrity
- Handle FAISS exceptions
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from datetime import datetime
import json


class DimensionMismatchError(Exception):
    """Raised when embedding dimension doesn't match index."""
    pass


class DuplicateChunkError(Exception):
    """Raised when duplicate chunks detected."""
    pass


class VectorInsertError(Exception):
    """Raised when FAISS insertion fails."""
    pass


class IndexSaveError(Exception):
    """Raised when index save fails."""
    pass


class DocumentRegistry:
    """Tracks document versions in vector store."""
    
    def __init__(self, registry_path: str = "data/vector_index/document_registry.json"):
        self.registry_path = Path(registry_path) if registry_path != ":memory:" else None
        if self.registry_path:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_registry()
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load existing registry or create new."""
        if self.registry_path and self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_registry(self):
        """Save registry to disk."""
        if self.registry_path is None:
            return
        with open(self.registry_path, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def register_document(self, doc_id: str, doc_name: str, version: int, chunks_count: int, faiss_range: Tuple[int, int]):
        """Register document version in registry."""
        if doc_id not in self.data:
            self.data[doc_id] = {
                "name": doc_name,
                "versions": []
            }
        
        # Mark previous versions as inactive
        for v in self.data[doc_id]["versions"]:
            v["active_version"] = False
        
        # Add new version
        self.data[doc_id]["versions"].append({
            "version": version,
            "upload_timestamp": datetime.utcnow().isoformat() + "Z",
            "active_version": True,
            "chunks_count": chunks_count,
            "faiss_range": list(faiss_range)
        })
        
        self._save_registry()
    
    def get_next_version(self, doc_id: str) -> int:
        """Get next version number for document."""
        if doc_id not in self.data:
            return 1
        return len(self.data[doc_id]["versions"]) + 1
    
    def is_indexed(self, doc_id: str) -> bool:
        """Check if document is already indexed."""
        return doc_id in self.data


class VectorManager:
    """Safe FAISS operations with validation."""
    
    def __init__(self, vector_store, embedding_dim: int = 384):
        self.vector_store = vector_store
        self.embedding_dim = embedding_dim
        self.registry = DocumentRegistry()
    
    def insert_with_validation(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert vectors with 5-step validation.
        
        Returns:
            {
                "inserted_count": int,
                "new_total": int,
                "faiss_indices": (start, end)
            }
        """
        print(f"\n[VECTOR INSERT] Starting validation...")
        
        # Step 1: Check dimension match
        if len(embeddings) == 0:
            raise VectorInsertError("No embeddings provided")
        
        actual_dim = embeddings[0].shape[0]
        print(f"  [1/5] Checking dimensions...")
        print(f"        Expected: {self.embedding_dim}, Got: {actual_dim}")
        
        if actual_dim != self.embedding_dim:
            raise DimensionMismatchError(
                f"Embedding dimension mismatch! Expected {self.embedding_dim}, got {actual_dim}"
            )
        print(f"  ✓ Dimensions match")
        
        # Step 2: Check for duplicates
        print(f"  [2/5] Checking for duplicates...")
        chunk_ids = [m["chunk_id"] for m in metadata_list]
        if len(chunk_ids) != len(set(chunk_ids)):
            duplicates = [cid for cid in chunk_ids if chunk_ids.count(cid) > 1]
            raise DuplicateChunkError(f"Duplicate chunk IDs: {duplicates}")
        print(f"  ✓ No duplicates found")
        
        # Step 3: Get current index size
        print(f"  [3/5] Checking index state...")
        current_ntotal = self.vector_store.index.ntotal if self.vector_store.index is not None else 0
        print(f"        Current vectors in index: {current_ntotal}")
        
        # Step 4: Insert into index
        print(f"  [4/5] Inserting vectors...")
        try:
            # Convert to float32 if needed
            if embeddings.dtype != np.float32:
                embeddings = embeddings.astype(np.float32)
            
            self.vector_store.add_embeddings(embeddings, metadata_list)
        except Exception as e:
            raise VectorInsertError(f"FAISS insertion failed: {str(e)}")
        
        print(f"  ✓ {len(embeddings)} vectors inserted")
        
        # Step 5: Verify insertion
        print(f"  [5/5] Verifying insertion...")
        new_ntotal = self.vector_store.index.ntotal
        expected_ntotal = current_ntotal + len(embeddings)
        
        print(f"        New total: {new_ntotal}, Expected: {expected_ntotal}")
        
        if new_ntotal != expected_ntotal:
            raise VectorInsertError(
                f"Index verification failed! Expected {expected_ntotal} vectors, got {new_ntotal}. "
                f"Possible index corruption."
            )
        
        print(f"  ✓ Verification passed")
        
        # Step 6: Save index
        print(f"\n[INDEX SAVE] Persisting to disk...")
        try:
            self.vector_store.save()
            print(f"  ✓ Index saved successfully")
        except Exception as e:
            raise IndexSaveError(f"Index save failed: {str(e)}")
        
        # Step 7: Register in document registry
        doc_id = metadata_list[0]["document_id"] if metadata_list else "unknown"
        doc_name = metadata_list[0]["document_name"] if metadata_list else "unknown"
        version = metadata_list[0]["version"] if metadata_list else 1
        faiss_range = (current_ntotal, new_ntotal - 1)
        
        self.registry.register_document(doc_id, doc_name, version, len(metadata_list), faiss_range)
        
        return {
            "inserted_count": len(embeddings),
            "new_total": new_ntotal,
            "faiss_indices": faiss_range
        }
    
    def get_next_version(self, doc_id: str) -> int:
        """Get next version number for document."""
        return self.registry.get_next_version(doc_id)
    
    def is_indexed(self, doc_id: str) -> bool:
        """Check if document is already in index."""
        return self.registry.is_indexed(doc_id)
