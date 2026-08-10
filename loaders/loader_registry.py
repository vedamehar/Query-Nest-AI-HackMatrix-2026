"""
Loader registry - maps file extensions to loader classes.
"""

from pathlib import Path
from typing import Type
from loaders.base_loader import BaseLoader, LoaderError, UnsupportedFileTypeError
from loaders.pdf_loader import PDFLoader
from loaders.markdown_loader import MarkdownLoader
from loaders.csv_loader import CSVLoader
from loaders.text_loader import TextLoader


class LoaderRegistry:
    """Maps file extensions to loader classes."""
    
    _loaders = {
        ".pdf": PDFLoader,
        ".md": MarkdownLoader,
        ".markdown": MarkdownLoader,
        ".csv": CSVLoader,
        ".txt": TextLoader,
    }
    
    @classmethod
    def get_loader(cls, file_path: str) -> BaseLoader:
        """Get appropriate loader for file."""
        ext = Path(file_path).suffix.lower()
        
        if ext not in cls._loaders:
            raise UnsupportedFileTypeError(
                f"No loader for {ext}. Supported: {list(cls._loaders.keys())}"
            )
        
        return cls._loaders[ext]()
    
    @classmethod
    def register_loader(cls, extension: str, loader_class: Type[BaseLoader]):
        """Register new loader for extension."""
        cls._loaders[extension.lower()] = loader_class
    
    @classmethod
    def get_supported_extensions(cls):
        """Get all supported extensions."""
        return list(cls._loaders.keys())
