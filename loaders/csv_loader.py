"""
CSV document loader.
"""

import csv
from pathlib import Path
from typing import Dict, Any
from loaders.base_loader import BaseLoader, LoaderError


class CSVLoader(BaseLoader):
    """Load CSV files into readable text format."""
    
    SUPPORTED_EXTENSIONS = [".csv"]
    
    def load(self, file_path: str) -> str:
        """Convert CSV to readable text format."""
        text = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    text += f"\n--- Record {idx + 1} ---\n"
                    for key, value in row.items():
                        text += f"{key}: {value}\n"
        except Exception as e:
            raise LoaderError(f"CSV extraction failed: {str(e)}")
        
        return text
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract CSV structure."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                row_count = sum(1 for _ in reader)
            
            return {
                "columns": headers,
                "column_count": len(headers),
                "row_count": row_count,
                "language": "en"
            }
        except Exception:
            return {"columns": [], "row_count": 0}
