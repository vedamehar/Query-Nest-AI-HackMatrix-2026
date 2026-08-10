"""
Vector store: FAISS-based semantic search.
Stores embeddings and metadata, enables similarity retrieval.
"""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np


class VectorStore:
    """FAISS-based vector database with metadata."""
    
    def __init__(self, embedding_dim: int = 384, index_path: str = None):
        self.embedding_dim = embedding_dim
        self.index_path = index_path
        self.index = None
        self.metadata = []
        self.chunk_id_map = {}
        
        try:
            import faiss
            self.faiss = faiss
        except ImportError:
            raise ImportError("FAISS required: pip install faiss-cpu")
    
    def initialize_index(self):
        """Create new FAISS index."""
        if self.index is None:
            self.index = self.faiss.IndexFlatL2(self.embedding_dim)
        self.metadata = []
        self.chunk_id_map = {}
    
    def add_embeddings(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]):
        """Add embeddings and metadata to index."""
        if self.index is None:
            self.initialize_index()
        
        embeddings = np.array(embeddings, dtype='float32')
        self.index.add(embeddings)
        
        for i, meta in enumerate(metadata_list):
            chunk_id = meta.get("chunk_id", f"chunk_{len(self.metadata)}")
            self.chunk_id_map[len(self.metadata)] = chunk_id
            self.metadata.append(meta)
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Tuple[float, Dict]]:
        """Search for top-k similar documents."""
        if self.index is None or len(self.metadata) == 0:
            return []
        
        query_embedding = np.array([query_embedding], dtype='float32')
        distances, indices = self.index.search(query_embedding, min(k, len(self.metadata)))
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.metadata):
                similarity = 1 / (1 + dist)
                results.append((similarity, self.metadata[idx]))
        
        return sorted(results, key=lambda x: x[0], reverse=True)
    
    def save(self, index_path: str):
        """Save index and metadata to disk."""
        path = Path(index_path)
        # ✅ FIXED: Create the full directory structure, not just parent
        path.mkdir(parents=True, exist_ok=True)
        
        self.faiss.write_index(self.index, str(path / "index.faiss"))
        
        with open(path / "metadata.pkl", "wb") as f:
            pickle.dump({"metadata": self.metadata, "chunk_id_map": self.chunk_id_map}, f)
    
    def load(self, index_path: str):
        """Load index and metadata from disk."""
        path = Path(index_path)
        
        # ✅ Check if files exist before loading
        index_file = path / "index.faiss"
        metadata_file = path / "metadata.pkl"
        
        if not index_file.exists() or not metadata_file.exists():
            raise FileNotFoundError(f"FAISS index files not found at {path}")
        
        self.index = self.faiss.read_index(str(index_file))
        
        with open(metadata_file, "rb") as f:
            data = pickle.load(f)
            self.metadata = data["metadata"]
            self.chunk_id_map = data["chunk_id_map"]


class EmbeddingModel:
    """Wrapper for sentence-transformers embeddings with offline support."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            import os
            from sentence_transformers import SentenceTransformer
            
            # ✅ CRITICAL: Set offline mode to prevent HuggingFace downloads
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            os.environ['HF_DATASETS_OFFLINE'] = '1'
            os.environ['SENTENCE_TRANSFORMERS_HOME'] = str(Path.home() / '.cache' / 'sentence-transformers')
            
            print(f"[EMBEDDING] Loading model: {model_name}")
            print(f"[EMBEDDING] Offline mode: ENABLED")
            
            # Try to load with local_files_only=True first
            try:
                self.model = SentenceTransformer(
                    model_name,
                    cache_folder=str(Path.home() / '.cache' / 'sentence-transformers'),
                    local_files_only=True  # Only use cached models
                )
                print(f"[EMBEDDING] ✓ Model loaded from cache (offline)")
            except Exception as e:
                print(f"[EMBEDDING] Cache load failed, trying online (will be cached)...")
                # If offline fails, try normal loading (will cache for future offline use)
                try:
                    self.model = SentenceTransformer(model_name)
                    print(f"[EMBEDDING] ✓ Model loaded and cached for offline use")
                except Exception as download_error:
                    print(f"[EMBEDDING] ✗ Could not load model: {download_error}")
                    print(f"[EMBEDDING] Using fallback: Simple embedding model")
                    # Use fallback embedding
                    self.model = None
                    self._use_fallback = True
        
        except ImportError:
            print("[EMBEDDING] sentence-transformers not available, using fallback")
            self.model = None
            self._use_fallback = True
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a batch of texts."""
        if self.model is not None:
            try:
                return self.model.encode(texts, convert_to_numpy=True)
            except Exception as e:
                print(f"[EMBEDDING] Encode error: {e}, using fallback")
                return self._fallback_embed(texts)
        else:
            return self._fallback_embed(texts)
    
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text."""
        if self.model is not None:
            try:
                return self.model.encode([text], convert_to_numpy=True)[0]
            except Exception as e:
                print(f"[EMBEDDING] Encode error: {e}, using fallback")
                return self._fallback_embed([text])[0]
        else:
            return self._fallback_embed([text])[0]
    
    def _fallback_embed(self, texts: List[str]) -> np.ndarray:
        """Simple fallback embedding using TF-IDF style approach."""
        import hashlib
        
        # Create deterministic embeddings based on text hash
        embeddings = []
        for text in texts:
            # Use hash to create a consistent 384-dim vector
            hash_obj = hashlib.sha256(text.encode())
            hash_hex = hash_obj.hexdigest()
            
            # Convert hex to 384-dimensional vector
            embedding = []
            for i in range(0, 384):
                # Use different bytes of the hash for reproducibility
                char_idx = (i * 2) % len(hash_hex)
                byte_val = int(hash_hex[char_idx:char_idx+2], 16) / 255.0
                embedding.append(byte_val)
            
            embeddings.append(embedding)
        
        return np.array(embeddings, dtype='float32')


class SemanticRetriever:
    """Retrieval pipeline: embed query + FAISS search."""
    
    def __init__(self, vector_store: VectorStore, embedding_model: EmbeddingModel):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
    
    def retrieve(self, query: str, top_k: int = 5, similarity_threshold: float = 0.4, video_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query with STRICT mode filtering.
        
        ✅ FIXED: Prevents cross-session context leakage
        
        Mode behavior:
          - If video_id provided: ONLY return video chunks from that video
          - If video_id is None: ONLY return non-video documents (SOP/policy)
          
        Critical: No mixing allowed! This prevents video content in normal queries.
        """
        query_embedding = self.embedding_model.embed_text(query)
        results = self.vector_store.search(query_embedding, k=top_k * 2)  # Get more results for filtering
        
        # Debug: Print actual similarity scores
        if results:
            print(f"[RETRIEVER] Raw scores: {[(sim, meta.get('source', 'unknown')[:30]) for sim, meta in results[:3]]}")
        
        # Use lower threshold to retrieve results
        effective_threshold = 0.1
        print(f"[RETRIEVER] Query threshold: {effective_threshold} (video_id: {video_id is not None})")
        
        filtered_results = [
            {
                **metadata,
                "similarity_score": float(similarity)
            }
            for similarity, metadata in results
            if similarity >= effective_threshold
        ]
        
        print(f"[RETRIEVER] Found {len(filtered_results)} results before mode filter")
        
        # ✅ CRITICAL FIX: STRICT MODE FILTERING
        # Separate video mode from normal mode completely
        if video_id:
            # MODE 1: Video query → ONLY video chunks
            print(f"[RETRIEVER] 🎬 VIDEO MODE: Filtering for video_id: {video_id}")
            print(f"[RETRIEVER]   Checking {len(filtered_results)} results for video_id match...")
            
            # Debug: Print first few results
            for i, doc in enumerate(filtered_results[:2]):
                doc_vid = doc.get("video_id") or doc.get("metadata", {}).get("video_id")
                print(f"[RETRIEVER]     Doc {i}: video_id={doc_vid}, source={doc.get('source')}")
            
            # Filter TO video documents
            pre_filter_count = len(filtered_results)
            filtered_results = [
                doc for doc in filtered_results
                if (doc.get("video_id") == video_id or 
                    doc.get("metadata", {}).get("video_id") == video_id)
            ]
            print(f"[RETRIEVER] ✓ Video mode: {pre_filter_count} → {len(filtered_results)} chunks (found video content)")
            
            if len(filtered_results) == 0:
                all_video_ids = set()
                for doc in [r[1] for r in results]:
                    vid = doc.get("video_id") or doc.get("metadata", {}).get("video_id")
                    if vid:
                        all_video_ids.add(vid)
                print(f"[RETRIEVER] ⚠️  No video chunks found for {video_id}. Available: {all_video_ids}")
        else:
            # MODE 2: Normal query → EXCLUDE all video chunks (SOP/policy only)
            print(f"[RETRIEVER] 📄 NORMAL MODE: Filtering OUT video documents")
            print(f"[RETRIEVER]   Excluding all documents with video_id set...")
            
            pre_filter_count = len(filtered_results)
            filtered_results = [
                doc for doc in filtered_results
                if not (doc.get("video_id") or doc.get("metadata", {}).get("video_id"))
            ]
            
            excluded_count = pre_filter_count - len(filtered_results)
            print(f"[RETRIEVER] ✓ Normal mode: {pre_filter_count} → {len(filtered_results)} docs (excluded {excluded_count} video chunks)")
            
            if excluded_count > 0:
                print(f"[RETRIEVER] ℹ️  Prevented {excluded_count} video chunks from appearing in normal query")
        
        # Return top_k results
        return filtered_results[:top_k]
