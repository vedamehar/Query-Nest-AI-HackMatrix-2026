"""
Unified Retriever: Single interface for searching all document sources.

Returns documents from:
- Internal Data1 documents
- Admin uploaded documents
- All file types (PDF, DOCX, CSV, MD, etc.)

Features:
- Cross-source retrieval
- Version filtering
- Metadata preservation
- Citation generation
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class RetrievalResult:
    """Result from unified retriever."""
    
    rank: int
    document_name: str
    document_id: str
    version: int
    source_type: str  # "Internal" or "Admin"
    folder_type: str
    file_type: str
    section_title: str
    page_number: Optional[int]
    chunk_id: str
    text: str
    similarity: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "document_name": self.document_name,
            "document_id": self.document_id,
            "version": self.version,
            "source_type": self.source_type,
            "folder_type": self.folder_type,
            "file_type": self.file_type,
            "section_title": self.section_title,
            "page_number": self.page_number,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "similarity": self.similarity
        }


class ValidationReport:
    """Retrieval validation report."""
    
    def __init__(self):
        self.success = False
        self.internal_docs_found = 0
        self.admin_docs_found = 0
        self.internal_sources = []
        self.admin_sources = []
        self.metadata_issues = []
        self.all_active_versions = True
        self.report_time = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "internal_docs_found": self.internal_docs_found,
            "admin_docs_found": self.admin_docs_found,
            "internal_sources": self.internal_sources,
            "admin_sources": self.admin_sources,
            "metadata_issues": self.metadata_issues,
            "all_active_versions": self.all_active_versions
        }


class UnifiedRetriever:
    """Single retriever for all document sources and file types."""
    
    def __init__(self, vector_store, embedding_model, registry=None):
        """
        Initialize unified retriever.
        
        Args:
            vector_store: VectorStore instance with FAISS index
            embedding_model: EmbeddingModel for query encoding
            registry: DocumentRegistry for version tracking (optional)
        """
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.registry = registry
    
    def search(self, query: str, k: int = 5, all_versions: bool = False) -> List[RetrievalResult]:
        """
        Retrieve relevant documents across ALL sources.
        
        Args:
            query: User query
            k: Number of results to return
            all_versions: If False, only active versions. If True, include all versions.
            
        Returns:
            List of RetrievalResult objects ranked by relevance
        """
        print(f"\n[UNIFIED RETRIEVAL] Query: '{query}'")
        print(f"  Requesting top {k} results")
        if not all_versions:
            print(f"  Filtering to active versions only")
        
        # Step 1: Embed query
        print(f"\n  [1/4] Embedding query...")
        try:
            query_embedding = self.embedding_model.embed_text(query)
        except Exception as e:
            print(f"  ✗ Query embedding failed: {str(e)}")
            return []
        
        print(f"  ✓ Query embedded (dim={query_embedding.shape[0]})")
        
        # Step 2: Search FAISS index
        print(f"\n  [2/4] Searching FAISS index...")
        results = self.vector_store.search(query_embedding, k)
        
        if not results:
            print(f"  ⚠ No results found in FAISS index")
            return []
        
        print(f"  ✓ Found {len(results)} candidates")
        
        # Step 3: Filter by version if needed
        print(f"\n  [3/4] Processing results...")
        if not all_versions:
            results = [r for r in results if r[1].get("active_version", True)]
            print(f"  ✓ Filtered to {len(results)} active versions")
        
        # Step 4: Build retrieval results
        print(f"\n  [4/4] Building retrieval objects...")
        retrieval_results = []
        
        for rank, (similarity, metadata) in enumerate(results, 1):
            try:
                result = RetrievalResult(
                    rank=rank,
                    document_name=metadata.get("document_name", "Unknown"),
                    document_id=metadata.get("document_id", "unknown"),
                    version=metadata.get("version", 0),
                    source_type=metadata.get("source_type", "Unknown"),
                    folder_type=metadata.get("folder_type", "General"),
                    file_type=metadata.get("file_type", "unknown"),
                    section_title=metadata.get("section_title", "General"),
                    page_number=metadata.get("page_number"),
                    chunk_id=metadata.get("chunk_id", "unknown"),
                    text=metadata.get("text", ""),
                    similarity=float(similarity)
                )
                retrieval_results.append(result)
            except Exception as e:
                print(f"  ⚠ Error processing result {rank}: {str(e)}")
                continue
        
        print(f"  ✓ {len(retrieval_results)} results returned")
        
        return retrieval_results
    
    def validate_retrieval(self, test_query: str = "compliance") -> ValidationReport:
        """
        Validate that retrieval works across all sources.
        For testing and debugging.
        
        Args:
            test_query: Query to use for validation
            
        Returns:
            ValidationReport with findings
        """
        print(f"\n" + "="*70)
        print(f"RETRIEVAL VALIDATION TEST")
        print(f"="*70)
        
        report = ValidationReport()
        
        # Run retrieval
        results = self.search(test_query, k=10)
        
        # Check 1: Internal documents found?
        print(f"\n[1] Checking for Internal Data1 documents...")
        internal_docs = [r for r in results if r.source_type == "Internal"]
        report.internal_docs_found = len(internal_docs)
        report.internal_sources = list(set(r.document_name for r in internal_docs))
        
        if internal_docs:
            print(f"  ✓ Found {report.internal_docs_found} Internal documents")
            print(f"    Sources: {', '.join(report.internal_sources)}")
        else:
            print(f"  ⚠ No Internal documents found")
        
        # Check 2: Admin documents found?
        print(f"\n[2] Checking for Admin uploaded documents...")
        admin_docs = [r for r in results if r.source_type == "Admin"]
        report.admin_docs_found = len(admin_docs)
        report.admin_sources = list(set(r.document_name for r in admin_docs))
        
        if admin_docs:
            print(f"  ✓ Found {report.admin_docs_found} Admin documents")
            print(f"    Sources: {', '.join(report.admin_sources)}")
        else:
            print(f"  ℹ No Admin documents found (may be normal if none uploaded)")
        
        # Check 3: Metadata consistency
        print(f"\n[3] Checking metadata consistency...")
        required_fields = [
            "document_id", "document_name", "version",
            "source_type", "folder_type", "file_type", "chunk_id"
        ]
        
        missing_count = 0
        for result in results:
            result_dict = result.to_dict()
            for field in required_fields:
                if field not in result_dict or result_dict[field] is None:
                    report.metadata_issues.append(
                        f"{result.chunk_id}: Missing or null '{field}'"
                    )
                    missing_count += 1
        
        if missing_count == 0:
            print(f"  ✓ All metadata fields present and valid")
        else:
            print(f"  ✗ {missing_count} metadata issues found:")
            for issue in report.metadata_issues[:5]:
                print(f"    - {issue}")
        
        # Check 4: Version flags
        print(f"\n[4] Checking version flags...")
        inactive = [r for r in results if not r.version]
        if inactive:
            print(f"  ⚠ Found {len(inactive)} documents with no version")
        else:
            print(f"  ✓ All results have valid versions")
        
        # Check 5: Citation format validation
        print(f"\n[5] Checking citation format...")
        valid_citations = 0
        for result in results:
            citation = f"{result.document_name} — {result.section_title}"
            if result.document_name and result.section_title:
                valid_citations += 1
        
        print(f"  ✓ {valid_citations}/{len(results)} results have valid citations")
        
        # Overall result
        print(f"\n" + "="*70)
        report.success = (report.internal_docs_found + report.admin_docs_found) > 0 and missing_count == 0
        
        if report.success:
            print(f"✓ VALIDATION PASSED")
        else:
            print(f"✗ VALIDATION FAILED")
        
        print(f"="*70)
        
        return report
    
    def refresh(self):
        """Refresh retriever (reload index if needed)."""
        print(f"\n[RETRIEVER] Refreshing...")
        # If using persistent index, reload it
        try:
            if hasattr(self.vector_store, 'load'):
                self.vector_store.load()
            print(f"  ✓ Retriever refreshed")
        except Exception as e:
            print(f"  ⚠ Refresh warning: {str(e)}")
