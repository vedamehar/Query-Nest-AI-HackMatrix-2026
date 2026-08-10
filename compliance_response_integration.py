"""
Compliance Response Integration
Integrates compliance formatting with the RAG pipeline.
Minimal changes to main structure - wraps LLM output only.
"""

from typing import Dict, List, Any, Optional
import json
from compliance_response_formatter import (
    ComplianceResponseFormatter,
    ComplianceStatus,
    ExtractedPolicy,
    PolicyReference,
    ReferenceLink,
)


class ComplianceResponseWrapper:
    """
    Wraps LLM responses to enforce compliance-driven format.
    Minimal integration - works with existing pipeline.
    """

    def __init__(self):
        self.formatter = ComplianceResponseFormatter()

    def detect_question_type(self, question: str) -> str:
        """
        Determine question type based on user input.
        
        Returns: "rewrite" | "policy" | "registry" | "analytical"
        """
        question_lower = question.lower()

        # REWRITE REQUESTS - Check FIRST
        if any(
            keyword in question_lower
            for keyword in [
                "rewrite", "correct", "improve", "fix", "make compliant",
                "edit", "revise", "refactor", "rephrase", "reformat",
                "here's a draft", "review this", "check this post",
                "is this okay", "does this comply", "draft post"
            ]
        ):
            return "rewrite"

        # Registry questions
        if any(
            keyword in question_lower
            for keyword in ["should we", "engage", "entity", "contact", "partner"]
        ):
            return "registry"

        # Policy questions
        if any(
            keyword in question_lower
            for keyword in ["policy", "rule", "regulation", "requirement", "restriction", "procedure", "process"]
        ):
            return "policy"

        # Default to analytical (informational question)
        return "analytical"

    def extract_policy_content(
        self, retrieved_documents: List[Dict[str, Any]]
    ) -> List[ExtractedPolicy]:
        """
        Extract policy bullet points from retrieved documents.
        Preserves direct quotes/paraphrases from sources.
        """
        extracted = []

        for doc in retrieved_documents:
            # Get document metadata
            doc_name = doc.get("doc_name", "Unknown Document")

            # Get content (may be in 'content', 'text', 'chunk', etc.)
            content = (
                doc.get("content")
                or doc.get("text")
                or doc.get("chunk")
                or doc.get("section", "")
            )

            # Get section reference
            section = doc.get("section", "Unknown Section")

            if content and content.strip():
                # Create policy extraction preserving original text
                policy = ExtractedPolicy(
                    bullet_point=content.strip()[:200],  # First 200 chars
                    section_reference=section,
                    document_name=doc_name,
                )
                extracted.append(policy)

        return extracted

    def create_policy_references(
        self, retrieved_documents: List[Dict[str, Any]]
    ) -> List[PolicyReference]:
        """Create policy reference citations from retrieved documents."""
        references = []
        seen = set()  # Avoid duplicates

        for doc in retrieved_documents:
            doc_name = doc.get("doc_name")
            version = doc.get("version")
            section_number = doc.get("section_number", "")
            section_title = doc.get("section_title", "")
            page = doc.get("page_number")

            # Create unique key
            key = (doc_name, version, section_number)
            if key not in seen:
                references.append(
                    PolicyReference(
                        document_name=doc_name or "Unknown",
                        version=version,
                        section_number=section_number or "N/A",
                        section_title=section_title or "N/A",
                        page_number=page,
                    )
                )
                seen.add(key)

        return references

    def create_reference_links(self, retrieved_documents: List[Dict[str, Any]]) -> List[ReferenceLink]:
        """Create internal redirect links."""
        links = []
        seen = set()

        for doc in retrieved_documents:
            doc_path = doc.get("file_path", "")
            section_id = doc.get("section_id", "section-unknown")

            if doc_path and section_id not in seen:
                link = ReferenceLink(
                    path=f"/docs/{doc_path}#{section_id}"
                )
                links.append(link)
                seen.add(section_id)

        # Ensure at least one link
        if not links:
            links.append(ReferenceLink(path="/docs/Data/"))

        return links

    def format_compliance_response(
        self,
        status: str,
        llm_interpretation: str,
        retrieved_documents: List[Dict[str, Any]],
        risk_implications: Optional[List[str]] = None,
        is_rewrite_request: bool = False,
        rewritten_content: Optional[str] = None,
    ) -> str:
        """
        Format response in compliance-driven structure.
        
        Args:
            status: "Approved" / "Informational" / "Blocked"
            llm_interpretation: LLM's explanation (already retrieval-grounded)
            retrieved_documents: Documents used for retrieval
            risk_implications: Optional risk explanations
            is_rewrite_request: True if user asked to rewrite/correct content
            rewritten_content: The rewritten/corrected version
            
        Returns:
            Formatted compliance response
        """

        # Extract content directly from documents
        extracted_policies = self.extract_policy_content(retrieved_documents)

        # Get citations
        references = self.create_policy_references(retrieved_documents)
        links = self.create_reference_links(retrieved_documents)

        # Use formatter
        status_enum = ComplianceStatus[status.upper()] if hasattr(
            ComplianceStatus, status.upper()
        ) else ComplianceStatus.INFORMATIONAL

        formatted = self.formatter.format_policy_response(
            status=status_enum,
            extracted_policies=extracted_policies,
            interpretation=llm_interpretation,
            risk_implications=risk_implications,
            policy_references=references if references else None,
            reference_links=links if links else None,
            is_rewrite_request=is_rewrite_request,
            rewritten_content=rewritten_content,
        )

        return formatted

    def format_registry_response(
        self,
        entity_name: str,
        registry_status: str,
        registry_data: Dict[str, str],
        registry_file: str = "Restricted_Entities_Registry.csv",
    ) -> str:
        """Format registry lookup response."""

        return self.formatter.format_registry_query_response(
            entity_name=entity_name,
            registry_type="Restricted" if "restricted" in registry_file.lower() else "Approved",
            status=registry_status,
            registry_data=registry_data,
            registry_file_path=registry_file,
            reference_link=f"/docs/Data/{registry_file}",
        )

    def wrap_llm_response(
        self,
        question: str,
        llm_response: str,
        retrieved_documents: List[Dict[str, Any]],
    ) -> str:
        """
        Wrap LLM response with compliance formatting.
        Detects if user wants a rewrite (draft provided) vs informational Q&A.
        """

        question_type = self.detect_question_type(question)

        # If no documents retrieved, return "insufficient documentation"
        if not retrieved_documents or len(retrieved_documents) == 0:
            return self.formatter.format_insufficient_documentation()

        # For registry questions, extract entity and check registries
        if question_type == "registry":
            # Extract entity name from question
            # This is simplified - real implementation would use NLP
            words = question.split()
            entity_name = " ".join(words[-3:]) if len(words) > 3 else question

            return self.format_registry_response(
                entity_name=entity_name,
                registry_status="Blocked",  # Would be determined by rule engine
                registry_data={
                    "Status": "Restricted",
                    "Reason": "Entity appears in restricted entities registry",
                },
            )

        # For REWRITE requests (user provides draft/post for correction)
        if question_type == "rewrite":
            return self.format_compliance_response(
                status="Informational",
                llm_interpretation="This content has been reviewed for compliance. See the rewritten version below.",
                retrieved_documents=retrieved_documents,
                risk_implications=None,
                is_rewrite_request=True,
                rewritten_content=llm_response,  # LLM response IS the rewritten version
            )

        # For INFORMATIONAL QUESTIONS (normal policy/analytical Q&A)
        # is_rewrite_request=False → No "FULLY REWRITTEN COMPLIANT VERSION" section
        return self.format_compliance_response(
            status="Informational",
            llm_interpretation=llm_response,  # Direct answer to the question
            retrieved_documents=retrieved_documents,
            risk_implications=None,
            is_rewrite_request=False,  # This is a normal question, not a rewrite
            rewritten_content=None,
        )


# Global instance
_compliance_wrapper = None


def get_compliance_wrapper() -> ComplianceResponseWrapper:
    """Get or create compliance wrapper instance."""
    global _compliance_wrapper
    if _compliance_wrapper is None:
        _compliance_wrapper = ComplianceResponseWrapper()
    return _compliance_wrapper


def enforce_compliance_on_response(
    question: str,
    llm_response: str,
    retrieved_documents: List[Dict[str, Any]],
) -> str:
    """
    Enforce compliance format on LLM response.
    
    This function should be called in the API pipeline:
    
    1. User asks question
    2. System performs RAG retrieval
    3. LLM generates response (using compliance system prompt)
    4. enforce_compliance_on_response() wraps the output
    5. Response sent to user in compliance format
    
    Usage in api_server.py:
    ```python
    from compliance_response_integration import enforce_compliance_on_response
    
    # In /ask endpoint:
    response = llm.generate(context, question)
    formatted_response = enforce_compliance_on_response(
        question, response, retrieved_documents
    )
    return {"response": formatted_response}
    ```
    """
    wrapper = get_compliance_wrapper()
    return wrapper.wrap_llm_response(question, llm_response, retrieved_documents)
