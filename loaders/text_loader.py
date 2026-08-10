"""
Plain text document loader.
"""

from pathlib import Path
from typing import Dict, Any
from loaders.base_loader import BaseLoader, LoaderError


class TextLoader(BaseLoader):
    """Load plain text files."""
    
    SUPPORTED_EXTENSIONS = [".txt"]
    
    def load(self, file_path: str) -> str:
        """Load text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise LoaderError(f"Text load failed: {str(e)}")
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract text metadata."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            return {
                "line_count": len(lines),
                "language": "en"
            }
        except Exception:
            return {"language": "en"}
