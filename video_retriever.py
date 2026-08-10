"""
Video-Aware Retriever: Filters FAISS results by video_id when requested.

Supports:
- Video-specific retrieval (search only within a single video)
- Cross-video retrieval (search across all videos and SOPs)
- Metadata preservation for proper citations
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class VideoRetrievalResult:
    """Result from video-aware retrieval."""
    
    chunk_id: str
    video_id: str
    filename: str
    text: str
    similarity_score: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "video_id": self.video_id,
            "filename": self.filename,
            "text": self.text,
            "similarity": self.similarity_score,
            "source": "video",
            "metadata": self.metadata
        }


class VideoRetriever:
    """Performs video-aware FAISS retrieval."""
    
    def __init__(self, faiss_index: Any, metadata_store: Dict[int, Dict]):
        """
        Initialize retriever.
        
        Args:
            faiss_index: FAISS index object
            metadata_store: Dict mapping FAISS indices to metadata
        """
        self.faiss_index = faiss_index
        self.metadata_store = metadata_store
    
    def _build_video_mask(self, video_id: str, k: int = 1000) -> Optional[List[bool]]:
        """
        Build boolean mask for FAISS to filter by video_id.
        
        Args:
            video_id: Video ID to filter for
            k: Maximum number of indices to check
        
        Returns:
            Boolean mask or None if video not found
        """
        mask = []
        found_video = False
        
        for idx in range(min(k, len(self.metadata_store))):
            metadata = self.metadata_store.get(idx, {})
            
            if metadata.get("video_id") == video_id:
                mask.append(True)
                found_video = True
            else:
                mask.append(False)
        
        if not found_video:
            print(f"[VIDEO_RETRIEVER] Warning: No chunks found for video_id: {video_id}")
            return None
        
        return mask
    
    def retrieve_video_specific(
        self,
        query_embedding: List[float],
        video_id: str,
        k: int = 5
    ) -> List[VideoRetrievalResult]:
        """
        Retrieve chunks from a specific video only.
        
        Args:
            query_embedding: Embedding vector of query
            video_id: Video ID to search within
            k: Number of results to return
        
        Returns:
            List of VideoRetrievalResult objects
        """
        print(f"[VIDEO_RETRIEVER] Searching video_id={video_id[:8]}... for {k} chunks")
        
        # Build mask for this video
        mask = self._build_video_mask(video_id)
        
        if not mask:
            print(f"[VIDEO_RETRIEVER] No chunks found for video: {video_id}")
            return []
        
        # Note: Standard FAISS doesn't support direct masking
        # Alternative: collect candidates and filter
        candidates = self._search_with_filter(query_embedding, mask, k)
        
        return candidates
    
    def retrieve_all_sources(
        self,
        query_embedding: List[float],
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve from all sources (videos + SOPs).
        
        Args:
            query_embedding: Embedding vector of query
            k: Number of results to return
        
        Returns:
            List of result dictionaries
        """
        print(f"[VIDEO_RETRIEVER] Searching all sources for {k} chunks")
        
        # Standard FAISS search (no filtering)
        distances, indices = self.faiss_index.search(
            [[float(x) for x in query_embedding]],
            k=k
        )
        
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx == -1:  # Invalid result
                continue
            
            metadata = self.metadata_store.get(int(idx), {})
            
            result = {
                "chunk_id": metadata.get("chunk_id", f"chunk_{idx}"),
                "text": metadata.get("text", ""),
                "source": metadata.get("source", "unknown"),
                "video_id": metadata.get("video_id"),
                "filename": metadata.get("filename"),
                "similarity": float(distance),
                "metadata": metadata
            }
            results.append(result)
        
        return results
    
    def _search_with_filter(
        self,
        query_embedding: List[float],
        mask: List[bool],
        k: int
    ) -> List[VideoRetrievalResult]:
        """
        Search FAISS and filter results by mask.
        
        Args:
            query_embedding: Query embedding
            mask: Boolean mask for filtering
            k: Number of results to return
        
        Returns:
            Filtered results
        """
        # Get more candidates than k to account for filtering
        oversampling = min(k * 3, len(mask))
        
        distances, indices = self.faiss_index.search(
            [[float(x) for x in query_embedding]],
            k=oversampling
        )
        
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx == -1:
                continue
            
            idx = int(idx)
            
            # Check mask
            if idx < len(mask) and not mask[idx]:
                continue  # Skip this result
            
            metadata = self.metadata_store.get(idx, {})
            
            result = VideoRetrievalResult(
                chunk_id=metadata.get("chunk_id", f"chunk_{idx}"),
                video_id=metadata.get("video_id", "unknown"),
                filename=metadata.get("filename", "unknown"),
                text=metadata.get("text", ""),
                similarity_score=float(distance),
                metadata=metadata
            )
            results.append(result)
            
            if len(results) >= k:
                break
        
        print(f"[VIDEO_RETRIEVER] ✓ Retrieved {len(results)} chunks")
        return results
    
    def get_video_chunks(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks belonging to a specific video.
        
        Args:
            video_id: Video ID
        
        Returns:
            List of chunk metadata
        """
        chunks = []
        for idx, metadata in self.metadata_store.items():
            if metadata.get("video_id") == video_id:
                chunks.append(metadata)
        
        return chunks
    
    def get_videos_in_index(self) -> List[str]:
        """Get list of all videos currently indexed."""
        video_ids = set()
        for metadata in self.metadata_store.values():
            if metadata.get("source") == "video":
                video_id = metadata.get("video_id")
                if video_id:
                    video_ids.add(video_id)
        
        return sorted(list(video_ids))


class VideoRetrieverFactory:
    """Factory for creating video-aware retrievers."""
    
    @staticmethod
    def create_from_vector_store(vector_store: Any) -> VideoRetriever:
        """
        Create retriever from existing vector store.
        
        Args:
            vector_store: Vector store instance with FAISS index and metadata
        
        Returns:
            VideoRetriever instance
        """
        if not hasattr(vector_store, 'index'):
            raise ValueError("Vector store must have 'index' attribute (FAISS index)")
        
        if not hasattr(vector_store, 'metadata'):
            raise ValueError("Vector store must have 'metadata' attribute")
        
        return VideoRetriever(
            faiss_index=vector_store.index,
            metadata_store=vector_store.metadata
        )
