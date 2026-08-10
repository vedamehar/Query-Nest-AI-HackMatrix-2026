"""
Base loader abstract class for all document loaders.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any


class LoaderError(Exception):
    """Base exception for loader errors."""
    pass


class UnsupportedFileTypeError(LoaderError):
    """Raised when file type is not supported."""
    pass


class BaseLoader(ABC):
    """Abstract base class for all document loaders."""
    
    SUPPORTED_EXTENSIONS = []
    
    @abstractmethod
    def load(self, file_path: str) -> str:
        """Load document and return extracted text."""
        pass
    
    @abstractmethod
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract structural metadata from document."""
        pass
    
    def validate_file(self, file_path: str) -> bool:
        """Check if file is readable."""
        try:
            Path(file_path).stat()
            return True
        except Exception:
            return False
