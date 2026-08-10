"""
Video Manager: Orchestrates video upload, transcription, and indexing.

Responsibilities:
- Accept video uploads (MP4 files)
- Generate unique video_id (UUID)
- Extract audio using FFmpeg
- Transcribe audio using Whisper
- Store transcript with metadata
- Trigger embedding and FAISS indexing
- Maintain video registry
"""

import os
import uuid
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import traceback

# Local FFmpeg installation (fully offline)
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

# For transcription (will be lazy-loaded)
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class VideoManager:
    """Manages video upload, transcription, and metadata."""
    
    def __init__(self, data_dir: str = "data/videos", whisper_model: str = "base"):
        """Initialize video manager."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.whisper_model_name = whisper_model
        self.whisper_model = None  # Lazy-loaded
        
        self.registry_file = self.data_dir.parent / "video_registry.json"
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load video registry from disk."""
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_registry(self):
        """Save video registry to disk."""
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2, default=str)
    
    def _get_whisper_model(self):
        """Lazy-load Whisper model (loaded once at first use)."""
        if not WHISPER_AVAILABLE:
            raise ImportError("whisper package not installed. Install with: pip install openai-whisper")
        
        if self.whisper_model is None:
            print(f"[VIDEO_MANAGER] Loading Whisper model '{self.whisper_model_name}'...")
            self.whisper_model = whisper.load_model(self.whisper_model_name)
            print(f"[VIDEO_MANAGER] ✓ Whisper model loaded")
        
        return self.whisper_model
    
    def upload_video(self, file_path: str, original_filename: str, metadata: Optional[Dict] = None) -> Tuple[str, Dict]:
        """
        Upload and prepare video for transcription.
        
        Args:
            file_path: Path to uploaded MP4 file
            original_filename: Original filename from upload
            metadata: Additional metadata (title, tags, etc.)
        
        Returns:
            (video_id, video_metadata)
        """
        try:
            # Generate video ID
            video_id = str(uuid.uuid4())
            
            # Create video-specific directory
            video_dir = self.data_dir / video_id
            video_dir.mkdir(parents=True, exist_ok=True)
            
            # Save original video
            video_path = video_dir / "original.mp4"
            if os.path.exists(file_path):
                shutil.move(file_path, str(video_path))
            else:
                # If file_path is already in right location
                video_path = Path(file_path)
            
            print(f"[VIDEO_MANAGER] ✓ Video saved: {video_path}")
            
            # Get file size
            file_size_mb = video_path.stat().st_size / (1024 * 1024)
            
            # Create metadata
            video_metadata = {
                "video_id": video_id,
                "type": "video",
                "filename": original_filename,
                "uploaded_by": metadata.get("uploaded_by", "admin") if metadata else "admin",
                "upload_timestamp": datetime.utcnow().isoformat(),
                "duration_seconds": None,  # Will be set after transcription
                "file_size_mb": round(file_size_mb, 2),
                "transcript_length": 0,
                "chunk_count": 0,
                "vector_indexed": False,
                "index_timestamp": None,
                "status": "uploaded",
                "metadata": metadata or {}
            }
            
            # Store in registry
            self.registry[video_id] = video_metadata
            self._save_registry()
            
            print(f"[VIDEO_MANAGER] ✓ Video registered: {video_id}")
            
            return video_id, video_metadata
        
        except Exception as e:
            print(f"[VIDEO_MANAGER] ✗ Upload failed: {e}")
            traceback.print_exc()
            raise
    
    def extract_audio(self, video_id: str) -> str:
        """
        Extract audio from video using FFmpeg.
        
        Args:
            video_id: Video ID
        
        Returns:
            Path to extracted audio file
        """
        try:
            video_dir = self.data_dir / video_id
            video_path = video_dir / "original.mp4"
            audio_path = video_dir / "audio.wav"
            
            if not video_path.exists():
                raise FileNotFoundError(f"Video not found: {video_path}")
            
            # FFmpeg command to extract audio
            command = [
                FFMPEG_PATH,
                "-i", str(video_path),
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # 16-bit PCM
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",  # Mono
                "-y",  # Overwrite output
                str(audio_path)
            ]
            
            print(f"[VIDEO_MANAGER] Extracting audio: {video_path}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
            
            print(f"[VIDEO_MANAGER] ✓ Audio extracted: {audio_path}")
            return str(audio_path)
        
        except Exception as e:
            print(f"[VIDEO_MANAGER] ✗ Audio extraction failed: {e}")
            traceback.print_exc()
            raise
    
    def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe audio using Whisper.
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Transcribed text
        """
        try:
            model = self._get_whisper_model()
            
            print(f"[VIDEO_MANAGER] Transcribing audio: {audio_path}")
            result = model.transcribe(audio_path, verbose=False)
            transcript_text = result.get("text", "")
            
            print(f"[VIDEO_MANAGER] ✓ Transcription complete ({len(transcript_text)} chars)")
            return transcript_text
        
        except Exception as e:
            print(f"[VIDEO_MANAGER] ✗ Transcription failed: {e}")
            traceback.print_exc()
            raise
    
    def save_transcript(self, video_id: str, transcript_text: str) -> str:
        """
        Save transcript to file.
        
        Args:
            video_id: Video ID
            transcript_text: Transcribed text
        
        Returns:
            Path to transcript file
        """
        try:
            video_dir = self.data_dir / video_id
            transcript_path = video_dir / "transcript.txt"
            
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            
            print(f"[VIDEO_MANAGER] ✓ Transcript saved: {transcript_path}")
            
            # Update registry
            if video_id in self.registry:
                self.registry[video_id]["transcript_length"] = len(transcript_text)
                self.registry[video_id]["status"] = "transcribed"
                self._save_registry()
            
            return str(transcript_path)
        
        except Exception as e:
            print(f"[VIDEO_MANAGER] ✗ Save transcript failed: {e}")
            traceback.print_exc()
            raise
    
    def process_video_complete(self, video_id: str, chunk_count: int):
        """
        Mark video as fully processed and indexed.
        
        Args:
            video_id: Video ID
            chunk_count: Number of chunks created
        """
        try:
            if video_id in self.registry:
                self.registry[video_id]["vector_indexed"] = True
                self.registry[video_id]["index_timestamp"] = datetime.utcnow().isoformat()
                self.registry[video_id]["chunk_count"] = chunk_count
                self.registry[video_id]["status"] = "indexed"
                self._save_registry()
            
            print(f"[VIDEO_MANAGER] ✓ Video marked as indexed: {video_id}")
        
        except Exception as e:
            print(f"[VIDEO_MANAGER] ✗ Mark indexed failed: {e}")
            traceback.print_exc()
    
    def get_video_info(self, video_id: str) -> Optional[Dict]:
        """Get metadata for a video."""
        return self.registry.get(video_id)
    
    def list_videos(self) -> list:
        """List all videos in registry."""
        return list(self.registry.values())
    
    def get_videos_by_status(self, status: str) -> list:
        """Get videos filtered by status."""
        return [v for v in self.registry.values() if v.get("status") == status]


# Required import
import shutil
