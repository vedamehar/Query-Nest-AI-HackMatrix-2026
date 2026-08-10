"""
Integrated Video Transcription Handler
Directly integrates Whisper + FFmpeg into main RAG system

This module handles:
- Video upload orchestration
- Auto-transcription with Whisper (model cached at startup)
- Transcript chunking & embedding
- FAISS insertion with video metadata
- Video-specific RAG filtering
"""

import os
import uuid
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import shutil
import threading

# Local FFmpeg installation (fully offline)
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFMPEG_DIR = r"C:\ffmpeg\bin"

# Add FFmpeg to PATH so Whisper can find it
if FFMPEG_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
    print(f"[VIDEO] ✓ Added FFmpeg to PATH: {FFMPEG_DIR}")

# Transcription
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Global Whisper model (loaded once at startup)
_whisper_model = None

def _clear_whisper_cache():
    """Clear corrupted Whisper model cache - run FIRST before any load attempt."""
    print("[VIDEO] Clearing Whisper model cache...")
    cache_paths = [
        Path.home() / ".cache" / "huggingface" / "hub",
        Path.home() / "AppData" / "Local" / "cache" / "huggingface" / "hub",
    ]
    
    for cache_dir in cache_paths:
        if not cache_dir.exists():
            continue
        
        whisper_dirs = list(cache_dir.glob("models--openai--whisper-*"))
        for whisper_dir in whisper_dirs:
            try:
                import shutil as sh
                sh.rmtree(whisper_dir)
                print(f"[VIDEO] ✓ Cleared: {whisper_dir}")
            except Exception as e:
                print(f"[VIDEO] Could not clear {whisper_dir}: {e}")

def load_whisper_model(model_name: str = "tiny", clear_cache_first: bool = False):
    """Load Whisper model globally (cached) with automatic cache repair."""
    global _whisper_model
    
    if _whisper_model is None:
        if not WHISPER_AVAILABLE:
            raise ImportError("whisper required: pip install openai-whisper")
        
        # Clear cache on first load to avoid checksum errors
        if clear_cache_first:
            _clear_whisper_cache()
        
        print(f"[VIDEO] Loading Whisper model '{model_name}'...")
        
        try:
            _whisper_model = whisper.load_model(model_name)
            print(f"[VIDEO] ✓ Model loaded successfully")
        
        except RuntimeError as e:
            error_msg = str(e)
            if "SHA256 checksum" in error_msg or "checksum" in error_msg.lower():
                print(f"[VIDEO] ⚠️ Checksum mismatch detected")
                print(f"[VIDEO] Clearing cache and retrying...")
                _clear_whisper_cache()
                # Retry with fresh download
                _whisper_model = whisper.load_model(model_name)
                print(f"[VIDEO] ✓ Model loaded after cache clear")
            else:
                raise
    
    return _whisper_model


class VideoTranscriptionHandler:
    """Main handler for video transcription in RAG system."""
    
    def __init__(self, data_dir: str = "data/videos"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.data_dir.parent / "video_registry.json"
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load video registry."""
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_registry(self):
        """Save video registry."""
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2, default=str)
    
    def _process_video_background(self, video_id: str, file_path: str, filename: str):
        """Process video in background thread (transcription + embedding)."""
        try:
            video_dir = self.data_dir / video_id
            audio_path = video_dir / "audio.wav"
            
            # Extract audio using FFmpeg
            video_path = video_dir / "original.mp4"
            command = [
                FFMPEG_PATH, "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
                str(audio_path)
            ]
            print(f"[VIDEO-BG] Extracting audio for {video_id}...")
            result = subprocess.run(command, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
            
            if not audio_path.exists():
                raise RuntimeError(f"Audio extraction failed: {audio_path}")
            
            print(f"[VIDEO-BG] ✓ Audio extracted: {audio_path}")
            
            # Transcribe with Whisper
            print(f"[VIDEO-BG] Transcribing audio...")
            model = load_whisper_model("tiny")
            print(f"[VIDEO-BG] Model loaded, transcribing {audio_path}...")
            transcription_result = model.transcribe(str(audio_path), verbose=False, language="en")
            transcript_text = transcription_result.get("text", "")
            print(f"[VIDEO-BG] ✓ Transcribed ({len(transcript_text)} chars)")
            
            # Save transcript
            transcript_path = video_dir / "transcript.txt"
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            
            # Update registry
            if video_id in self.registry:
                self.registry[video_id]["status"] = "transcribed"
                self.registry[video_id]["transcript_length"] = len(transcript_text)
                self.registry[video_id]["vector_indexed"] = True
                self._save_registry()
            
            print(f"[VIDEO-BG] ✓ Processing complete: {video_id}")
        
        except Exception as e:
            print(f"[VIDEO-BG] ✗ Error processing {video_id}: {type(e).__name__}: {str(e)}")
            if video_id in self.registry:
                self.registry[video_id]["status"] = "error"
                self.registry[video_id]["error"] = str(e)
                self._save_registry()
    
    def upload_and_transcribe_async(self, file_path: str, filename: str) -> Tuple[str, Dict]:
        """
        Upload video and start background transcription.
        Returns immediately with video_id and status.
        
        Returns:
            (video_id, metadata)
        """
        print(f"\n[VIDEO] Starting async upload: {filename}")
        
        # Step 1: Generate video_id and create directory
        video_id = str(uuid.uuid4())
        video_dir = self.data_dir / video_id
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 2: Save original video
        video_path = video_dir / "original.mp4"
        shutil.copy(file_path, str(video_path))
        print(f"[VIDEO] ✓ Video saved: {video_path}")
        
        # Step 3: Create metadata (processing status)
        metadata = {
            "video_id": video_id,
            "type": "video",
            "filename": filename,
            "uploaded_at": datetime.utcnow().isoformat(),
            "transcript_length": 0,
            "status": "processing",  # Processing in background
            "vector_indexed": False
        }
        
        # Save registry
        self.registry[video_id] = metadata
        self._save_registry()
        
        print(f"[VIDEO] ✓ Upload queued: {video_id}")
        print(f"[VIDEO] Starting background transcription...")
        
        # Step 4: Start background thread for transcription
        thread = threading.Thread(
            target=self._process_video_background,
            args=(video_id, file_path, filename),
            daemon=False
        )
        thread.start()
        
        return video_id, metadata
    
    def upload_and_transcribe(self, file_path: str, filename: str) -> Tuple[str, Dict, str]:
        """
        Upload video, transcribe, chunk, and prepare for embedding.
        
        Returns:
            (video_id, metadata, transcript_text)
        """
        print(f"\n[VIDEO] Starting upload/transcription: {filename}")
        
        # Step 1: Generate video_id and create directory
        video_id = str(uuid.uuid4())
        video_dir = self.data_dir / video_id
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 2: Save original video
        video_path = video_dir / "original.mp4"
        shutil.copy(file_path, str(video_path))
        print(f"[VIDEO] ✓ Video saved: {video_path}")
        
        # Step 3: Extract audio using FFmpeg
        audio_path = video_dir / "audio.wav"
        command = [
            FFMPEG_PATH, "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
            str(audio_path)
        ]
        print(f"[VIDEO] Extracting audio...")
        print(f"[VIDEO] FFmpeg command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f"[VIDEO] FFmpeg stdout: {result.stdout}")
            print(f"[VIDEO] FFmpeg stderr: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        
        # Verify audio file was created
        if not audio_path.exists():
            raise RuntimeError(f"Audio extraction failed: File not found at {audio_path}")
        
        audio_size = audio_path.stat().st_size
        if audio_size < 1000:  # Sanity check - audio should be at least 1KB
            print(f"[VIDEO] ⚠️  WARNING: Audio file seems too small ({audio_size} bytes)")
        
        print(f"[VIDEO] ✓ Audio extracted: {audio_path} ({audio_size} bytes)")
        
        # Step 4: Transcribe with Whisper
        print(f"[VIDEO] Transcribing audio...")
        try:
            model = load_whisper_model("tiny")
            print(f"[VIDEO] Model loaded, starting transcription of {audio_path}...")
            
            # Verify audio file exists and has content
            if not audio_path.exists():
                raise RuntimeError(f"Audio file not found: {audio_path}")
            audio_size = audio_path.stat().st_size
            if audio_size == 0:
                raise RuntimeError(f"Audio file is empty: {audio_path}")
            print(f"[VIDEO] Audio file size: {audio_size} bytes")
            
            transcription_result = model.transcribe(str(audio_path), verbose=False, language="en")
            transcript_text = transcription_result.get("text", "")
            
            # ✅ CHECK: Ensure we got actual transcript
            if not transcript_text or len(transcript_text.strip()) == 0:
                print(f"[VIDEO] ⚠️  WARNING: Whisper returned empty transcript")
                print(f"[VIDEO] Full result: {transcription_result}")
                # Check if result has segments
                segments = transcription_result.get("segments", [])
                if segments:
                    print(f"[VIDEO] Found {len(segments)} segments, extracting...")
                    transcript_text = " ".join([seg.get("text", "") for seg in segments])
                    print(f"[VIDEO] Reconstructed transcript: {len(transcript_text)} chars")
                else:
                    print(f"[VIDEO] No segments found - audio may be silent or invalid")
                    # Return minimal content so system doesn't fail completely
                    transcript_text = "[Silent or unrecognized audio]"
            
            print(f"[VIDEO] ✓ Transcribed ({len(transcript_text)} chars)")
        except Exception as e:
            print(f"[VIDEO] Transcription error: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Whisper transcription failed: {str(e)}")
        
        # Step 5: Save transcript
        transcript_path = video_dir / "transcript.txt"
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript_text)
        
        # Step 6: Create metadata
        metadata = {
            "video_id": video_id,
            "type": "video",
            "filename": filename,
            "uploaded_at": datetime.utcnow().isoformat(),
            "transcript_length": len(transcript_text),
            "status": "transcribed",
            "vector_indexed": False
        }
        
        # Save registry
        self.registry[video_id] = metadata
        self._save_registry()
        
        print(f"[VIDEO] ✓ Upload complete: {video_id}")
        return video_id, metadata, transcript_text
    
    def chunk_transcript(self, transcript: str, video_id: str, filename: str) -> List[Dict]:
        """
        Chunk transcript into semantic segments with metadata.
        
        Returns:
            List of chunk dicts ready for embedding
        """
        print(f"[VIDEO] Chunking transcript...")
        
        # ✅ NEW: Validate transcript has content
        if not transcript or len(transcript.strip()) == 0:
            print(f"[VIDEO] ⚠️  WARNING: Transcript is empty, returning placeholder chunk")
            return [{
                "chunk_id": f"vid_{video_id[:8]}_0000",
                "source": "video",
                "video_id": video_id,
                "filename": filename,
                "text": "[No speech detected in video]",
                "metadata": {
                    "type": "video",
                    "video_id": video_id,
                    "chunk_index": 0
                }
            }]
        
        chunks = []
        sentences = transcript.split('. ')
        
        current_chunk = []
        current_length = 0
        chunk_index = 0
        
        for sentence in sentences:
            # Skip empty sentences
            if not sentence.strip():
                continue
                
            if current_length + len(sentence) > 800 and current_chunk:
                # Save chunk
                chunk_text = '. '.join(current_chunk).strip()
                if chunk_text:  # Only add non-empty chunks
                    chunks.append({
                        "chunk_id": f"vid_{video_id[:8]}_{chunk_index:04d}",
                        "source": "video",
                        "video_id": video_id,
                        "filename": filename,
                        "text": chunk_text,
                        "metadata": {
                            "type": "video",
                            "video_id": video_id,
                            "chunk_index": chunk_index
                        }
                    })
                    chunk_index += 1
                current_chunk = []
                current_length = 0
            
            current_chunk.append(sentence)
            current_length += len(sentence)
        
        # Final chunk
        if current_chunk:
            chunk_text = '. '.join(current_chunk).strip()
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    "chunk_id": f"vid_{video_id[:8]}_{chunk_index:04d}",
                    "source": "video",
                    "video_id": video_id,
                    "filename": filename,
                    "text": chunk_text,
                    "metadata": {
                        "type": "video",
                        "video_id": video_id,
                        "chunk_index": chunk_index
                    }
                })
        
        print(f"[VIDEO] ✓ Created {len(chunks)} chunks")
        return chunks if chunks else [{
            "chunk_id": f"vid_{video_id[:8]}_0000",
            "source": "video",
            "video_id": video_id,
            "filename": filename,
            "text": "[No speech detected in video]",
            "metadata": {
                "type": "video",
                "video_id": video_id,
                "chunk_index": 0
            }
        }]
    
    def mark_indexed(self, video_id: str, chunk_count: int):
        """Mark video as indexed."""
        if video_id in self.registry:
            self.registry[video_id]["vector_indexed"] = True
            self.registry[video_id]["indexed_at"] = datetime.utcnow().isoformat()
            self.registry[video_id]["chunk_count"] = chunk_count
            self._save_registry()
    
    def get_videos(self) -> List[Dict]:
        """Get all videos."""
        return list(self.registry.values())
    
    def get_video_chunks_for_query(self, video_id: str, embeddings_data: Dict) -> List[str]:
        """
        Get all chunk indices for a specific video in FAISS.
        Used for filtering retrieval results.
        """
        chunk_indices = []
        for idx, metadata in embeddings_data.items():
            if metadata.get("metadata", {}).get("video_id") == video_id:
                chunk_indices.append(idx)
        return chunk_indices


# Singleton instance
_handler = None

def get_video_handler(data_dir: str = "data/videos") -> VideoTranscriptionHandler:
    """Get or create video handler singleton."""
    global _handler
    if _handler is None:
        _handler = VideoTranscriptionHandler(data_dir)
    return _handler
