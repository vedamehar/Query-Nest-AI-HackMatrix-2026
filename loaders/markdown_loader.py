"""
Markdown document loader.
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from loaders.base_loader import BaseLoader, LoaderError


class MarkdownLoader(BaseLoader):
    """Load Markdown files."""
    
    SUPPORTED_EXTENSIONS = [".md", ".markdown"]
    
    def load(self, file_path: str) -> str:
        """Load markdown as-is (headers preserved as section markers)."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise LoaderError(f"Markdown load failed: {str(e)}")
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract sections from markdown headers."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract headers
            sections = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
            
            return {
                "sections": sections,
                "language": "en",
                "header_count": len(sections)
            }
        except Exception:
            return {"sections": [], "language": "en"}
