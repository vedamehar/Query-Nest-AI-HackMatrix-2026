"""
Metadata Enforcer: Ensures retrieved documents have complete metadata.
Enforces traceable citations for compliance audits.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class DocumentMetadata:
    """Required metadata structure for citations."""
    document_name: str
    version: Optional[str] = "Unknown"
    section_number: Optional[str] = "Unknown"
    section_title: Optional[str] = "Unknown"
    page_number: Optional[int] = None
    source_path: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if metadata is sufficiently complete."""
        return bool(self.document_name and self.section_number and self.section_title)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_name": self.document_name,
            "version": self.version,
            "section_number": self.section_number,
            "section_title": self.section_title,
            "page_number": self.page_number,
            "source_path": self.source_path,
        }
    
    def format_for_citation(self) -> str:
        """Format metadata as citation text."""
        citation = f"{self.document_name}"
        
        if self.version and self.version != "Unknown":
            citation += f" (v{self.version})"
        
        if self.section_number and self.section_number != "Unknown":
            citation += f" — Section {self.section_number}"
        
        if self.section_title and self.section_title != "Unknown":
            citation += f": {self.section_title}"
        
        if self.page_number:
            citation += f" (p. {self.page_number})"
        
        return citation


class MetadataEnforcer:
    """
    Enforces complete metadata on all retrieved documents.
    Ensures citations are traceable and auditable.
    """
    
    @staticmethod
    def extract_metadata(doc: Dict[str, Any]) -> DocumentMetadata:
        """
        Extract metadata from document dictionary.
        Handles missing fields gracefully.
        """
        return DocumentMetadata(
            document_name=doc.get("doc_name") or doc.get("document_name") or "Unknown",
            version=doc.get("version") or "Unknown",
            section_number=doc.get("chunk_id") or doc.get("section_number") or "Unknown",
            section_title=doc.get("section_title") or "Unknown",
            page_number=doc.get("page_number"),
            source_path=doc.get("source_path") or doc.get("source"),
        )
    
    @staticmethod
    def validate_metadata(metadata: DocumentMetadata) -> tuple[bool, List[str]]:
        """
        Validate metadata completeness.
        
        Returns:
            (is_valid, list_of_issues)
        """
        issues = []
        
        if not metadata.document_name or metadata.document_name == "Unknown":
            issues.append("Missing document name")
        
        if not metadata.section_number or metadata.section_number == "Unknown":
            issues.append("Missing section number/chunk ID")
        
        if not metadata.section_title or metadata.section_title == "Unknown":
            issues.append("Missing section title")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def enrich_metadata_in_docs(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich document list with complete metadata.
        Inject "Metadata incomplete" flags where needed.
        """
        enriched = []
        
        for doc in documents:
            metadata = MetadataEnforcer.extract_metadata(doc)
            is_valid, issues = MetadataEnforcer.validate_metadata(metadata)
            
            enriched_doc = doc.copy()
            enriched_doc["_metadata"] = metadata.to_dict()
            enriched_doc["_metadata_valid"] = is_valid
            
            if not is_valid:
                enriched_doc["_metadata_note"] = (
                    "Metadata incomplete – citation may be unavailable. "
                    f"Issues: {', '.join(issues)}"
                )
            
            enriched.append(enriched_doc)
        
        return enriched
    
    @staticmethod
    def generate_citations(documents: List[Dict[str, Any]]) -> List[str]:
        """
        Generate properly formatted citations from documents.
        For use in POLICY REFERENCES section.
        """
        citations = []
        seen = set()  # Avoid duplicates
        
        for doc in documents:
            metadata = MetadataEnforcer.extract_metadata(doc)
            citation = metadata.format_for_citation()
            
            # Avoid duplicate citations
            if citation not in seen:
                citations.append(citation)
                seen.add(citation)
        
        return citations
    
    @staticmethod
    def generate_reference_links(documents: List[Dict[str, Any]]) -> List[str]:
        """
        Generate reference links for REFERENCE LINKS section.
        Format: /docs/document_path#section-x
        """
        links = []
        seen = set()
        
        for doc in documents:
            metadata = MetadataEnforcer.extract_metadata(doc)
            
            # Build path from document name and section
            doc_path = metadata.document_name.replace(".pdf", "").replace(".md", "").lower()
            section_anchor = metadata.section_number.lower().replace(" ", "-")
            
            link = f"/docs/{doc_path}#{section_anchor}"
            
            if link not in seen:
                links.append(link)
                seen.add(link)
        
        return links


# Singleton instance
_enforcer = MetadataEnforcer()


def extract_metadata(doc: Dict[str, Any]) -> DocumentMetadata:
    """Extract metadata from document."""
    return _enforcer.extract_metadata(doc)


def validate_metadata(metadata: DocumentMetadata) -> tuple[bool, List[str]]:
    """Validate metadata completeness."""
    return _enforcer.validate_metadata(metadata)


def enrich_documents_with_metadata(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich documents with complete metadata."""
    return _enforcer.enrich_metadata_in_docs(documents)


def generate_citations(documents: List[Dict[str, Any]]) -> List[str]:
    """Generate formatted citations."""
    return _enforcer.generate_citations(documents)


def generate_reference_links(documents: List[Dict[str, Any]]) -> List[str]:
    """Generate reference links."""
    return _enforcer.generate_reference_links(documents)
