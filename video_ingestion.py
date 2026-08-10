"""
Video Ingestion: Chunks and embeds video transcripts for FAISS indexing.

Pipeline:
1. Load transcript text
2. Split into semantic chunks (500-800 tokens)
3. Attach metadata (video_id, filename, etc.)
4. Generate embeddings
5. Insert into FAISS with metadata
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path


@dataclass
class VideoChunk:
    """Represents a single chunk from video transcript."""
    
    chunk_id: str
    video_id: str
    filename: str
    text: str
    token_count: int
    start_position: int  # Character position in original transcript
    end_position: int
    metadata: Dict[str, Any]
    
    def to_metadata_dict(self) -> Dict[str, Any]:
        """Convert to FAISS metadata format."""
        return {
            "chunk_id": self.chunk_id,
            "source": "video",
            "video_id": self.video_id,
            "filename": self.filename,
            "text": self.text,
            "start_pos": self.start_position,
            "end_pos": self.end_position,
            **self.metadata
        }


class VideoIngestion:
    """Chunks and embeds video transcripts."""
    
    # Approximate tokens per word (for simple estimation)
    TOKENS_PER_WORD = 0.75
    
    def __init__(self, min_chunk_size: int = 500, max_chunk_size: int = 800):
        """
        Initialize video ingestion.
        
        Args:
            min_chunk_size: Minimum tokens per chunk
            max_chunk_size: Maximum tokens per chunk
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (simple word-based approximation)."""
        words = len(text.split())
        return int(words * self.TOKENS_PER_WORD)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences (simple approach)."""
        # Split on common sentence endings
        sentences = []
        current = ""
        
        for char in text:
            current += char
            if char in '.!?\n':
                if current.strip():
                    sentences.append(current.strip())
                current = ""
        
        if current.strip():
            sentences.append(current.strip())
        
        return sentences
    
    def chunk_transcript(
        self,
        transcript_text: str,
        video_id: str,
        filename: str
    ) -> List[VideoChunk]:
        """
        Split transcript into semantic chunks with metadata.
        
        Args:
            transcript_text: Full transcript
            video_id: Video ID
            filename: Original video filename
        
        Returns:
            List of VideoChunk objects
        """
        chunks = []
        
        if not transcript_text or not transcript_text.strip():
            print(f"[VIDEO_INGESTION] Warning: Empty transcript for {video_id}")
            return chunks
        
        # Split into sentences
        sentences = self._split_into_sentences(transcript_text)
        print(f"[VIDEO_INGESTION] Split transcript into {len(sentences)} sentences")
        
        # Group sentences into chunks
        current_chunk = []
        current_tokens = 0
        chunk_index = 0
        char_position = 0
        
        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            
            # Check if adding this sentence would exceed max_chunk_size
            if current_tokens + sentence_tokens > self.max_chunk_size and current_chunk:
                # Finalize current chunk
                chunk_text = " ".join(current_chunk)
                start_pos = char_position
                char_position += len(chunk_text)
                
                chunk = self._create_chunk(
                    chunk_text=chunk_text,
                    chunk_index=chunk_index,
                    video_id=video_id,
                    filename=filename,
                    start_pos=start_pos,
                    end_pos=char_position
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Reset for next chunk
                current_chunk = []
                current_tokens = 0
            
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            start_pos = char_position
            char_position += len(chunk_text)
            
            chunk = self._create_chunk(
                chunk_text=chunk_text,
                chunk_index=chunk_index,
                video_id=video_id,
                filename=filename,
                start_pos=start_pos,
                end_pos=char_position
            )
            chunks.append(chunk)
        
        print(f"[VIDEO_INGESTION] Created {len(chunks)} chunks from transcript")
        return chunks
    
    def _create_chunk(
        self,
        chunk_text: str,
        chunk_index: int,
        video_id: str,
        filename: str,
        start_pos: int,
        end_pos: int
    ) -> VideoChunk:
        """Create a VideoChunk object."""
        chunk_id = f"vid_{video_id[:8]}_{chunk_index:04d}"
        
        return VideoChunk(
            chunk_id=chunk_id,
            video_id=video_id,
            filename=filename,
            text=chunk_text,
            token_count=self._estimate_tokens(chunk_text),
            start_position=start_pos,
            end_position=end_pos,
            metadata={
                "doc_name": filename.replace('.mp4', ''),
                "chunk_index": chunk_index,
                "upload_timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def prepare_for_embedding(self, chunks: List[VideoChunk]) -> List[str]:
        """
        Prepare chunk texts for embedding.
        
        Args:
            chunks: List of VideoChunk objects
        
        Returns:
            List of texts to embed
        """
        return [chunk.text for chunk in chunks]
    
    def add_embeddings_to_chunks(
        self,
        chunks: List[VideoChunk],
        embeddings: List[List[float]]
    ) -> List[Dict[str, Any]]:
        """
        Create FAISS-compatible entries with embeddings.
        
        Args:
            chunks: List of VideoChunk objects
            embeddings: List of embedding vectors
        
        Returns:
            List of FAISS entry dicts with embeddings
        """
        entries = []
        
        for chunk, embedding in zip(chunks, embeddings):
            entry = {
                "embedding": embedding,
                "metadata": chunk.to_metadata_dict()
            }
            entries.append(entry)
        
        return entries
    
    def create_metadata_entries(self, chunks: List[VideoChunk]) -> List[Dict[str, Any]]:
        """
        Create metadata entries for FAISS metadata index.
        
        Args:
            chunks: List of VideoChunk objects
        
        Returns:
            List of metadata dictionaries
        """
        return [chunk.to_metadata_dict() for chunk in chunks]


class VideoChunkingPipeline:
    """High-level pipeline for video transcript processing."""
    
    def __init__(self):
        """Initialize pipeline."""
        self.ingestion = VideoIngestion()
    
    def process_transcript(
        self,
        transcript_text: str,
        video_id: str,
        filename: str
    ) -> List[VideoChunk]:
        """
        Process transcript into chunks.
        
        Args:
            transcript_text: Full transcript text
            video_id: Video ID
            filename: Original video filename
        
        Returns:
            List of VideoChunk objects ready for embedding
        """
        print(f"[VIDEO_PIPELINE] Processing transcript: {filename} (video_id={video_id[:8]}...)")
        
        chunks = self.ingestion.chunk_transcript(
            transcript_text=transcript_text,
            video_id=video_id,
            filename=filename
        )
        
        print(f"[VIDEO_PIPELINE] ✓ Created {len(chunks)} chunks")
        return chunks
