"""
RAG Grounding Enforcer: Prevents LLM from hallucinating citations.

Core principle:
    LLM generates ONLY explanation text.
    Backend attaches citations from ACTUAL retrieved documents.
    NEVER trust LLM-generated document references.
"""
import re
from typing import Dict, List, Any, Optional, Tuple


class HallucinationDetector:
    """Detect if LLM hallucinated citations or file references."""
    
    # Patterns that indicate hallucinated citations
    HALLUCINATION_PATTERNS = [
        r'\.pdf(?:\s|—|–|$)',                    # Mentions .pdf files
        r'\.docx(?:\s|—|–|$)',                   # Mentions .docx files
        r'Section\s+\d+',                         # "Section 3.1" pattern
        r'Chapter\s+\d+',                         # "Chapter 2" pattern
        r'Page\s+\d+',                            # "Page 5" pattern
        r'/docs/',                                # File path patterns
        r'/policies/',                            # Policy path patterns
        r'Document[\s_]?\d+',                     # "Document 1" pattern
        r'Policy[\s_]?[A-Z]',                     # "Policy A" pattern
        r'—\s*\w+',                               # Em-dash followed by reference
        r'–\s*\w+',                               # En-dash followed by reference
        r'\[\w+(?:\.\w+)?\]',                     # [Reference] pattern
        r'\(\w+(?:\.\w+)?\)',                     # (Reference) pattern
    ]
    
    @staticmethod
    def has_hallucinated_citations(text: str) -> Tuple[bool, List[str]]:
        """
        Check if text contains hallucinated citations.
        
        Returns:
            (has_hallucinations, matched_patterns)
        """
        matches = []
        text_lower = text.lower()
        
        for pattern in HallucinationDetector.HALLUCINATION_PATTERNS:
            found = re.findall(pattern, text_lower, re.IGNORECASE)
            if found:
                matches.extend(found)
        
        return (len(matches) > 0, matches)
    
    @staticmethod
    def extract_hallucinated_references(text: str) -> Dict[str, List[str]]:
        """Extract different types of hallucinated references from text."""
        results = {
            "pdf_files": [],
            "sections": [],
            "pages": [],
            "paths": [],
        }
        
        # PDF files
        pdf_matches = re.findall(r'(\w+(?:\s\w+)*\.pdf)', text, re.IGNORECASE)
        results["pdf_files"] = list(set(pdf_matches))
        
        # Sections
        section_matches = re.findall(r'Section\s+([\d.]+)', text, re.IGNORECASE)
        results["sections"] = section_matches
        
        # Pages
        page_matches = re.findall(r'Page\s+(\d+)', text, re.IGNORECASE)
        results["pages"] = page_matches
        
        # Paths
        path_matches = re.findall(r'(/(?:docs|policies)/[\w/.-]+)', text)
        results["paths"] = path_matches
        
        return results


class ProperCitationGenerator:
    """Generate citations ONLY from actual retrieved document metadata."""
    
    @staticmethod
    def extract_citations_from_metadata(retrieved_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract proper citations directly from retrieved document metadata.
        
        NEVER from LLM text.
        
        Args:
            retrieved_documents: List of documents with metadata
            
        Returns:
            List of proper citations
        """
        citations = []
        
        for doc in retrieved_documents:
            # Must have at least these fields
            if not all(k in doc for k in ['source', 'metadata']):
                continue
            
            meta = doc['metadata']
            citation = {
                'document': doc.get('source', 'Unknown'),
                'page': meta.get('page_number', 'N/A'),
                'section': meta.get('section', 'N/A'),
                'chunk_id': meta.get('chunk_id', 'N/A'),
                'version': meta.get('version', '1.0'),
                'folder': meta.get('folder_type', 'Unknown'),
            }
            
            citations.append(citation)
        
        # Remove duplicates (same source + page + section)
        unique_citations = []
        seen = set()
        
        for cit in citations:
            key = (cit['document'], cit['page'], cit['section'])
            if key not in seen:
                seen.add(key)
                unique_citations.append(cit)
        
        return unique_citations
    
    @staticmethod
    def format_citation_for_display(citation: Dict[str, Any]) -> str:
        """
        Format citation in user-friendly format.
        
        Format: DocumentName.pdf — Section X (Page Y)
        """
        doc = citation['document']
        page = citation['page']
        section = citation['section']
        
        # Build citation string
        parts = [doc]
        
        if section and section != 'N/A':
            parts.append(f"Section {section}")
        
        if page and page != 'N/A':
            parts.append(f"Page {page}")
        
        return " — ".join(parts)
    
    @staticmethod
    def build_citations_section(retrieved_documents: List[Dict[str, Any]]) -> str:
        """
        Build complete citations section from actual documents.
        
        This is the ONLY way to add citations.
        """
        if not retrieved_documents:
            return "No sources referenced."
        
        citations = ProperCitationGenerator.extract_citations_from_metadata(retrieved_documents)
        
        if not citations:
            return "No sources referenced."
        
        # Format each citation
        formatted = []
        for cit in citations:
            formatted_cit = ProperCitationGenerator.format_citation_for_display(cit)
            formatted.append(f"• {formatted_cit}")
        
        section = "\n6️⃣ POLICY REFERENCES\n\n"
        section += "\n".join(formatted)
        
        return section


class RAGResponseProcessor:
    """Post-process LLM response to enforce proper grounding."""
    
    @staticmethod
    def clean_hallucinated_citations(text: str) -> str:
        """
        Remove all citation-like patterns from LLM text.
        
        Keep ONLY the explanation content.
        """
        # Remove PDF file mentions
        text = re.sub(r'\w+(?:\s\w+)*\.pdf', '[CITATION]', text, flags=re.IGNORECASE)
        
        # Remove "Section X.Y" patterns
        text = re.sub(r'Section\s+[\d.]+', '[CITATION]', text, flags=re.IGNORECASE)
        
        # Remove "Page N" patterns
        text = re.sub(r'Page\s+\d+', '[CITATION]', text, flags=re.IGNORECASE)
        
        # Remove file paths
        text = re.sub(r'/(?:docs|policies)/[\w/.-]+', '[CITATION]', text)
        
        # Remove em-dash references
        text = re.sub(r'—\s*(?:\w+(?:\.\w+)?|[\w\s]+)', '', text)
        text = re.sub(r'–\s*(?:\w+(?:\.\w+)?|[\w\s]+)', '', text)
        
        # Remove references in brackets/parens that look like citations
        text = re.sub(r'\[\w+(?:\.\w+)?\]', '[CITATION]', text)
        text = re.sub(r'\(\w+(?:\.\w+)?\)', '[CITATION]', text)
        
        return text.strip()
    
    @staticmethod
    def process_response(llm_response: str,
                        retrieved_documents: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        """
        Process LLM response to enforce RAG grounding.
        
        Steps:
        1. Detect hallucinated citations
        2. Remove them
        3. Attach proper citations from metadata
        4. Return processed response with validation
        
        Returns:
            (processed_response, validation_report)
        """
        validation_report = {
            "has_hallucinations": False,
            "hallucinated_patterns": [],
            "hallucinated_refs": {},
            "citations_attached": 0,
            "enforcement_applied": False,
        }
        
        # Step 1: Detect hallucinations
        has_hallucinations, patterns = HallucinationDetector.has_hallucinated_citations(llm_response)
        validation_report["has_hallucinations"] = has_hallucinations
        validation_report["hallucinated_patterns"] = patterns
        
        if has_hallucinations:
            print("[RAG] ⚠️  WARNING: Detected hallucinated citations in LLM response")
            print(f"[RAG] Patterns found: {patterns}")
            validation_report["hallucinated_refs"] = HallucinationDetector.extract_hallucinated_references(llm_response)
            validation_report["enforcement_applied"] = True
            
            # Step 2: Remove hallucinated content
            print("[RAG] Removing hallucinated citations...")
            llm_response = RAGResponseProcessor.clean_hallucinated_citations(llm_response)
        
        # Step 3: Attach proper citations
        if retrieved_documents:
            print("[RAG] Attaching proper citations from metadata...")
            citations_section = ProperCitationGenerator.build_citations_section(retrieved_documents)
            
            citations = ProperCitationGenerator.extract_citations_from_metadata(retrieved_documents)
            validation_report["citations_attached"] = len(citations)
            
            # Add citations to response
            if "6️⃣" not in llm_response and "POLICY REFERENCES" not in llm_response:
                llm_response = llm_response.rstrip() + "\n\n" + citations_section
            else:
                # Replace existing (likely hallucinated) citations section
                llm_response = re.sub(
                    r'6️⃣.*?(?=7️⃣|$)',
                    citations_section,
                    llm_response,
                    flags=re.DOTALL
                )
        
        return llm_response, validation_report


class StrictRAGPromptTemplate:
    """
    Prompt template that PREVENTS LLM from generating citations.
    
    Key principles:
    - Explicitly forbid LLM from creating citations
    - Only ask for explanation text
    - Mention that citations will be added by system
    """
    
    @staticmethod
    def get_system_prompt() -> str:
        """Get strict RAG system prompt with NO citation generation."""
        return """You are a COMPLIANCE-BOUND ENTERPRISE ASSISTANT.

CRITICAL: You must answer ONLY from the provided context documents.

IF THE CONTEXT DOES NOT CONTAIN THE ANSWER:
    Say: "I cannot find this information in our approved documents."

ANSWER FORMAT:
    Provide ONLY your explanation.
    Use these sections:
    
    1️⃣ COMPLIANCE STATUS
    State ONLY ONE: Approved | Conditionally Allowed | Blocked
    
    2️⃣ VIOLATIONS IDENTIFIED  
    If violations exist, use BULLET POINTS only.
    
    3️⃣ RISK LEVEL
    State ONLY ONE: Low | Medium | High | Critical
    
    4️⃣ REQUIRED CORRECTIONS
    Use BULLET POINTS only.
    
    5️⃣ FULLY REWRITTEN COMPLIANT VERSION
    Clean explanation paragraph.

IMPORTANT RESTRICTIONS:
    ✗ NEVER mention file names (.pdf, .docx, etc.)
    ✗ NEVER mention "Section 1.2" or page numbers
    ✗ NEVER mention document paths (/docs/, /policies/)
    ✗ NEVER add em-dashes followed by references (—)
    ✗ NEVER add brackets or parentheses with citations ([Doc], (Policy))
    ✗ NEVER reference files YOU CANNOT VERIFY in the context

WHY:
    Citations are added by the system from actual documents.
    You cannot see our file system structure.
    Avoid hallucinating document names.

CONFIDENCE:
    If you are unsure about information:
        Say so explicitly.
        Do not guess or invent references.

Your ONLY job: Explain the content from provided context.
Citations are handled by the backend."""
    
    @staticmethod
    def get_user_message_template() -> str:
        """Get user message template with context."""
        return """Use ONLY this context to answer:

{context}

User question: {question}

Answer format:
1️⃣ COMPLIANCE STATUS
2️⃣ VIOLATIONS IDENTIFIED
3️⃣ RISK LEVEL
4️⃣ REQUIRED CORRECTIONS
5️⃣ FULLY REWRITTEN COMPLIANT VERSION

Remember:
- Do NOT mention file names
- Do NOT mention section numbers
- Citations will be added by the system
- Answer only from the context above"""


# Usage Example
if __name__ == "__main__":
    # Example: Processing a response
    llm_text = """
    1️⃣ COMPLIANCE STATUS
    Approved
    
    2️⃣ VIOLATIONS IDENTIFIED
    None identified
    
    3️⃣ RISK LEVEL
    Low
    
    4️⃣ REQUIRED CORRECTIONS
    No corrections needed
    
    5️⃣ FULLY REWRITTEN COMPLIANT VERSION
    This action complies with our policies. As per Financial Management Best Practices.pdf — Section 2.1,
    all transactions must be documented. See also Organization Structure Guidelines.pdf, Page 15.
    
    6️⃣ POLICY REFERENCES
    Financial Management Best Practices.pdf — Section 2.1
    Organization Structure Guidelines.pdf — Page 15
    """
    
    retrieved_docs = [
        {
            "source": "Finance_Policy.pdf",
            "content": "All transactions must be documented...",
            "metadata": {
                "page_number": 5,
                "section": "2.1",
                "chunk_id": "chunk_123",
                "version": "1.0",
                "folder_type": "SOPs"
            }
        },
        {
            "source": "Organization.pdf",
            "content": "Organizational structure includes...",
            "metadata": {
                "page_number": 3,
                "section": "3.0",
                "chunk_id": "chunk_456",
                "version": "2.0",
                "folder_type": "Policies"
            }
        }
    ]
    
    # Process response
    processed, report = RAGResponseProcessor.process_response(llm_text, retrieved_docs)
    
    print("\n[HALLUCINATION DETECTION]")
    print(f"Has hallucinations: {report['has_hallucinations']}")
    print(f"Hallucinated patterns: {report['hallucinated_patterns']}")
    print(f"Enforcement applied: {report['enforcement_applied']}")
    print(f"Citations attached: {report['citations_attached']}")
    
    print("\n[PROCESSED RESPONSE]")
    print(processed)
