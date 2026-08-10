"""
Video Audit Logger: Tracks video operations for compliance and audit trails.

Logs:
- Video uploads
- Video transcriptions
- Video queries
- Compliance decisions on video queries
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path


class VideoAuditLogger:
    """Logs all video-related operations."""
    
    def __init__(self, log_dir: str = "logs/video_audit"):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / "video_audit.jsonl"
    
    def log_upload(
        self,
        video_id: str,
        filename: str,
        uploaded_by: str,
        file_size_mb: float,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Log video upload.
        
        Args:
            video_id: Unique video ID
            filename: Original filename
            uploaded_by: User who uploaded
            file_size_mb: File size in MB
            metadata: Additional metadata
        
        Returns:
            Log entry ID
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": "video_upload",
            "video_id": video_id,
            "filename": filename,
            "uploaded_by": uploaded_by,
            "file_size_mb": file_size_mb,
            "metadata": metadata or {}
        }
        
        return self._write_log(entry)
    
    def log_transcription(
        self,
        video_id: str,
        filename: str,
        transcript_length: int,
        chunk_count: int,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None
    ) -> int:
        """
        Log video transcription.
        
        Args:
            video_id: Video ID
            filename: Video filename
            transcript_length: Length of transcript in characters
            chunk_count: Number of chunks created
            duration_seconds: Video duration
            error: Error message if transcription failed
        
        Returns:
            Log entry ID
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": "video_transcription",
            "video_id": video_id,
            "filename": filename,
            "transcript_length": transcript_length,
            "chunk_count": chunk_count,
            "duration_seconds": duration_seconds,
            "status": "failed" if error else "success",
            "error": error
        }
        
        return self._write_log(entry)
    
    def log_video_query(
        self,
        query: str,
        video_id: str,
        user_id: str,
        chunks_used: List[str],
        compliance_status: str,
        model_version: str,
        response_length: int,
        processing_time_ms: int,
        ip_address: Optional[str] = None
    ) -> int:
        """
        Log video-specific query.
        
        Args:
            query: User query
            video_id: Video being queried
            user_id: User ID
            chunks_used: List of chunk IDs used
            compliance_status: "approved" or "blocked"
            model_version: LLM model used
            response_length: Length of response in characters
            processing_time_ms: Processing time in milliseconds
            ip_address: User IP address
        
        Returns:
            Log entry ID
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": "video_query",
            "query": query[:500],  # Truncate long queries
            "query_length": len(query),
            "video_id": video_id,
            "user_id": user_id,
            "chunks_used": chunks_used,
            "chunk_count": len(chunks_used),
            "compliance_status": compliance_status,
            "model_version": model_version,
            "response_length": response_length,
            "processing_time_ms": processing_time_ms,
            "ip_address": ip_address
        }
        
        return self._write_log(entry)
    
    def log_video_indexing(
        self,
        video_id: str,
        filename: str,
        chunk_count: int,
        embedding_model: str,
        index_time_ms: int,
        error: Optional[str] = None
    ) -> int:
        """
        Log video indexing operation.
        
        Args:
            video_id: Video ID
            filename: Video filename
            chunk_count: Number of chunks indexed
            embedding_model: Embedding model used
            index_time_ms: Time to index in milliseconds
            error: Error message if indexing failed
        
        Returns:
            Log entry ID
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": "video_indexing",
            "video_id": video_id,
            "filename": filename,
            "chunk_count": chunk_count,
            "embedding_model": embedding_model,
            "index_time_ms": index_time_ms,
            "status": "failed" if error else "success",
            "error": error
        }
        
        return self._write_log(entry)
    
    def log_video_deletion(
        self,
        video_id: str,
        filename: str,
        deleted_by: str,
        reason: Optional[str] = None
    ) -> int:
        """
        Log video deletion.
        
        Args:
            video_id: Video ID
            filename: Video filename
            deleted_by: User who deleted
            reason: Reason for deletion
        
        Returns:
            Log entry ID
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": "video_deletion",
            "video_id": video_id,
            "filename": filename,
            "deleted_by": deleted_by,
            "reason": reason
        }
        
        return self._write_log(entry)
    
    def _write_log(self, entry: Dict[str, Any]) -> int:
        """
        Write log entry to file.
        
        Args:
            entry: Log entry dictionary
        
        Returns:
            Line number in log file
        """
        try:
            # Read current line count
            line_count = 0
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    line_count = sum(1 for _ in f)
            
            # Append entry
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry, default=str) + '\n')
            
            return line_count + 1
        
        except Exception as e:
            print(f"[VIDEO_AUDIT] Error writing log: {e}")
            raise
    
    def get_video_audit_trail(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Get all audit entries for a specific video.
        
        Args:
            video_id: Video ID
        
        Returns:
            List of audit entries
        """
        entries = []
        
        if not self.log_file.exists():
            return entries
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    entry = json.loads(line)
                    if entry.get("video_id") == video_id:
                        entries.append(entry)
        
        except Exception as e:
            print(f"[VIDEO_AUDIT] Error reading audit trail: {e}")
        
        return entries
    
    def get_user_video_queries(self, user_id: str, video_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all video queries by a user (optionally filtered by video).
        
        Args:
            user_id: User ID
            video_id: Optional video ID filter
        
        Returns:
            List of query entries
        """
        entries = []
        
        if not self.log_file.exists():
            return entries
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    entry = json.loads(line)
                    
                    # Filter by operation and user
                    if entry.get("operation") != "video_query":
                        continue
                    
                    if entry.get("user_id") != user_id:
                        continue
                    
                    # Optional video_id filter
                    if video_id and entry.get("video_id") != video_id:
                        continue
                    
                    entries.append(entry)
        
        except Exception as e:
            print(f"[VIDEO_AUDIT] Error reading user queries: {e}")
        
        return entries
    
    def get_compliance_stats(self, video_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get compliance statistics from video queries.
        
        Args:
            video_id: Optional video ID filter
        
        Returns:
            Compliance statistics
        """
        stats = {
            "total_queries": 0,
            "approved": 0,
            "blocked": 0,
            "approval_rate": 0.0,
            "videos_queried": set()
        }
        
        if not self.log_file.exists():
            return stats
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    entry = json.loads(line)
                    
                    if entry.get("operation") != "video_query":
                        continue
                    
                    if video_id and entry.get("video_id") != video_id:
                        continue
                    
                    stats["total_queries"] += 1
                    
                    compliance_status = entry.get("compliance_status", "unknown")
                    if compliance_status == "approved":
                        stats["approved"] += 1
                    elif compliance_status == "blocked":
                        stats["blocked"] += 1
                    
                    stats["videos_queried"].add(entry.get("video_id"))
        
        except Exception as e:
            print(f"[VIDEO_AUDIT] Error computing stats: {e}")
        
        # Compute approval rate
        if stats["total_queries"] > 0:
            stats["approval_rate"] = stats["approved"] / stats["total_queries"]
        
        # Convert set to list for JSON serialization
        stats["videos_queried"] = sorted(list(stats["videos_queried"]))
        
        return stats
