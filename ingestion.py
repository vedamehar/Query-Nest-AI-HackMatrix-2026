"""
Document ingestion pipeline: PDF, Markdown, and text processing.
Chunks documents into 500-800 token segments with metadata.
"""
import os
from pathlib import Path
from typing import List, Dict, Any
import re

class DocumentChunk:
    def __init__(self, text: str, doc_name: str, section: str, page: int = None, chunk_id: str = None):
        self.text = text
        self.doc_name = doc_name
        self.section = section
        self.page = page
        self.chunk_id = chunk_id or f"{doc_name}_{section}_{page}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "doc_name": self.doc_name,
            "section": self.section,
            "page": self.page,
            "chunk_id": self.chunk_id
        }


class DocumentProcessor:
    """Process various document formats."""
    
    @staticmethod
    def count_tokens(text: str) -> int:
        """Rough token count (1 token ≈ 4 chars)."""
        return len(text) // 4
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into semantic chunks."""
        words = text.split()
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for word in words:
            word_tokens = DocumentProcessor.count_tokens(word)
            if current_tokens + word_tokens > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = current_chunk[-20:] if len(current_chunk) > 20 else []
                current_tokens = DocumentProcessor.count_tokens(" ".join(current_chunk))
            
            current_chunk.append(word)
            current_tokens += word_tokens
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return [c for c in chunks if len(c.strip()) > 50]
    
    @staticmethod
    def load_markdown(file_path: str) -> str:
        """Load Markdown file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @staticmethod
    def load_text(file_path: str) -> str:
        """Load plain text file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @staticmethod
    def load_pdf(file_path: str) -> str:
        """Load PDF using PyMuPDF (fitz)."""
        try:
            import fitz
            text = ""
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
            return text
        except ImportError:
            raise ImportError("PyMuPDF required: pip install PyMuPDF")


class DocumentIngestionPipeline:
    """End-to-end document ingestion with chunking and metadata."""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.processor = DocumentProcessor()
    
    def ingest(self, file_path: str) -> List[DocumentChunk]:
        """Ingest a single document."""
        file_path = Path(file_path)
        doc_name = file_path.stem
        suffix = file_path.suffix.lower()
        
        if suffix == ".pdf":
            text = self.processor.load_pdf(str(file_path))
        elif suffix in [".md", ".markdown"]:
            text = self.processor.load_markdown(str(file_path))
        elif suffix == ".txt":
            text = self.processor.load_text(str(file_path))
        else:
            raise ValueError(f"Unsupported format: {suffix}")
        
        chunks = self.processor.chunk_text(text, self.chunk_size, self.chunk_overlap)
        
        document_chunks = []
        for idx, chunk in enumerate(chunks):
            chunk_obj = DocumentChunk(
                text=chunk,
                doc_name=doc_name,
                section=f"Section_{idx}",
                page=None,
                chunk_id=f"{doc_name}_chunk_{idx}"
            )
            document_chunks.append(chunk_obj)
        
        return document_chunks
    
    def ingest_directory(self, directory: str) -> List[DocumentChunk]:
        """Ingest all documents in a directory."""
        all_chunks = []
        dir_path = Path(directory)
        
        for file_path in dir_path.rglob("*"):
            if file_path.suffix.lower() in [".pdf", ".md", ".markdown", ".txt"]:
                try:
                    chunks = self.ingest(str(file_path))
                    all_chunks.extend(chunks)
                    print(f"✓ Ingested: {file_path.name} ({len(chunks)} chunks)")
                except Exception as e:
                    print(f"✗ Failed to ingest {file_path.name}: {e}")
        
        return all_chunks
