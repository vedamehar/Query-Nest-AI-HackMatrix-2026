"""
PDF document loader using PyMuPDF.
"""

from pathlib import Path
from typing import Dict, Any
from loaders.base_loader import BaseLoader, LoaderError


class PDFLoader(BaseLoader):
    """Load PDF documents with page markers."""
    
    SUPPORTED_EXTENSIONS = [".pdf"]
    
    def load(self, file_path: str) -> str:
        """Extract text from PDF."""
        try:
            import fitz
        except ImportError:
            raise LoaderError("PyMuPDF required: pip install PyMuPDF")
        
        text = ""
        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc):
                text += f"\n--- PAGE {page_num + 1} ---\n"
                page_text = page.get_text()
                if page_text.strip():
                    text += page_text
            doc.close()
        except Exception as e:
            raise LoaderError(f"PDF extraction failed: {str(e)}")
        
        return text
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract PDF metadata."""
        try:
            import fitz
            doc = fitz.open(file_path)
            metadata = {
                "total_pages": len(doc),
                "title": doc.metadata.get("title", "") if doc.metadata else "",
                "author": doc.metadata.get("author", "") if doc.metadata else "",
                "language": "en"
            }
            doc.close()
            return metadata
        except Exception:
            return {"total_pages": 0, "language": "en"}
