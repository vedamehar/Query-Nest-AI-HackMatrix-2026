"""
Compliance-Driven Response Formatter
Enforces policy-grounded, retrieval-based response structure with citations and links.
Replaces generic rewriting with extracted content and source attribution.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ComplianceStatus(Enum):
    """Compliance decision status."""
    APPROVED = "Approved"
    INFORMATIONAL = "Informational"
    BLOCKED = "Blocked"


@dataclass
class ExtractedPolicy:
    """Extracted policy content from documents."""
    bullet_point: str
    section_reference: str
    document_name: str


@dataclass
class PolicyReference:
    """Policy citation metadata."""
    document_name: str
    version: Optional[str]
    section_number: str
    section_title: str
    page_number: Optional[str]


@dataclass
class ReferenceLink:
    """Internal redirect link."""
    path: str  # Format: /docs/<document_path>#section-x


class ComplianceResponseFormatter:
    """
    Formats responses in compliance-driven structure.
    
    For INFORMATIONAL QUESTIONS (normal Q&A):
    1. COMPLIANCE STATUS
    2. EXTRACTED POLICY CONTENT
    3. CLEAR ANSWER SUMMARY (NEW - for direct user-facing answer)
    4. RISK IMPLICATIONS (if applicable)
    5. POLICY REFERENCES
    6. REFERENCE LINKS
    
    For REWRITE REQUESTS (user provides draft/post):
    1. COMPLIANCE STATUS
    2. EXTRACTED POLICY CONTENT
    3. CLEAR ANSWER SUMMARY
    4. FULLY REWRITTEN COMPLIANT VERSION (ONLY for rewrites)
    5. RISK IMPLICATIONS
    6. POLICY REFERENCES
    7. REFERENCE LINKS
    """

    @staticmethod
    def format_policy_response(
        status: ComplianceStatus,
        extracted_policies: List[ExtractedPolicy],
        interpretation: str,
        risk_implications: Optional[List[str]] = None,
        policy_references: Optional[List[PolicyReference]] = None,
        reference_links: Optional[List[ReferenceLink]] = None,
        is_rewrite_request: bool = False,
        rewritten_content: Optional[str] = None,
    ) -> str:
        """
        Format policy/analytical question response.
        
        Args:
            status: Approval status (Approved/Informational/Blocked)
            extracted_policies: Bullet points with policy content
            interpretation: How policy applies to question (no hallucination)
            risk_implications: Operational/fraud/governance risks
            policy_references: Citation information
            reference_links: Internal redirect URLs
            is_rewrite_request: True if user asked to rewrite/correct content
            rewritten_content: The rewritten/corrected version (only if is_rewrite_request=True)
            
        Returns:
            Formatted response string with mandatory structure
        """
        lines = []

        # 1️⃣ COMPLIANCE STATUS
        lines.append("1️⃣ COMPLIANCE STATUS")
        lines.append(f"{status.value}")
        lines.append("")

        # 2️⃣ EXTRACTED POLICY CONTENT
        lines.append("2️⃣ EXTRACTED POLICY CONTENT")
        if extracted_policies:
            for policy in extracted_policies:
                lines.append(f"• {policy.bullet_point}")
                lines.append(f"  Section: {policy.section_reference}")
            lines.append("")
        else:
            lines.append("• No policy content retrieved")
            lines.append("")

        # 3️⃣ CLEAR ANSWER SUMMARY (NEW - mandatory for all questions)
        lines.append("3️⃣ CLEAR ANSWER SUMMARY")
        lines.append(interpretation)
        lines.append("")

        # 4️⃣ FULLY REWRITTEN COMPLIANT VERSION (ONLY for rewrite requests)
        if is_rewrite_request and rewritten_content:
            lines.append("4️⃣ FULLY REWRITTEN COMPLIANT VERSION")
            lines.append(rewritten_content)
            lines.append("")
            # Shift remaining sections down by 1 if rewrite is included
            risk_section = "5️⃣"
            ref_section = "6️⃣"
            link_section = "7️⃣"
        else:
            # NO rewrite section for normal Q&A
            risk_section = "4️⃣"
            ref_section = "5️⃣"
            link_section = "6️⃣"

        # RISK IMPLICATIONS
        if risk_implications:
            lines.append(f"{risk_section} RISK IMPLICATIONS")
            for risk in risk_implications:
                lines.append(f"• {risk}")
            lines.append("")
        else:
            lines.append(f"{risk_section} RISK IMPLICATIONS")
            lines.append("• No material risks identified")
            lines.append("")

        # POLICY REFERENCES
        lines.append(f"{ref_section} POLICY REFERENCES")
        if policy_references:
            for ref in policy_references:
                version_str = f" (v{ref.version})" if ref.version else ""
                page_str = f" | Page: {ref.page_number}" if ref.page_number else ""
                lines.append(f"• {ref.document_name}{version_str}")
                lines.append(f"  Section {ref.section_number}: {ref.section_title}{page_str}")
            lines.append("")
        else:
            lines.append("• Metadata incomplete – citation unavailable")
            lines.append("")

        # REFERENCE LINKS
        lines.append(f"{link_section} REFERENCE LINKS")
        if reference_links:
            for link in reference_links:
                lines.append(f"• {link.path}")
            lines.append("")
        else:
            lines.append("• Internal links unavailable")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_registry_query_response(
        entity_name: str,
        registry_type: str,  # "Restricted" or "Approved"
        status: str,  # "BLOCKED", "APPROVED", etc.
        registry_data: Dict[str, str],
        registry_file_path: str,
        reference_link: Optional[str] = None,
    ) -> str:
        """
        Format entity/registry lookup response.
        
        For questions like: "Should we engage with this investment blog?"
        
        Args:
            entity_name: The entity being queried
            registry_type: Which registry was checked
            status: Decision based on registry
            registry_data: Extracted registry fields
            registry_file_path: Path to registry file
            reference_link: Internal reference link
            
        Returns:
            Formatted registry response
        """
        lines = []

        # Decision
        lines.append("1️⃣ COMPLIANCE STATUS")
        lines.append(status)
        lines.append("")

        # Entity lookup
        lines.append("2️⃣ ENTITY LOOKUP RESULT")
        lines.append(f"Entity: {entity_name}")
        lines.append(f"Registry: {registry_type}_Entities_Registry")
        lines.append("")

        # Registry data
        lines.append("3️⃣ REGISTRY DATA")
        for key, value in registry_data.items():
            lines.append(f"• {key}: {value}")
        lines.append("")

        # Citation
        lines.append("4️⃣ POLICY REFERENCES")
        lines.append(f"• Registry File: {registry_file_path}")
        lines.append("")

        # Link
        lines.append("5️⃣ REFERENCE LINKS")
        if reference_link:
            lines.append(f"• {reference_link}")
        else:
            lines.append("• /docs/Data/Restricted_Entities_Registry.csv")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_insufficient_documentation() -> str:
        """Return when no documents support the answer."""
        return "I do not have sufficient internal documentation to answer this question."

    @staticmethod
    def format_structured_output(
        sections: Dict[str, str],
        include_spacing: bool = True,
    ) -> str:
        """
        Generic structured output formatter.
        
        Args:
            sections: Dict of section_title -> content
            include_spacing: Add blank lines between sections
            
        Returns:
            Formatted output
        """
        lines = []
        
        for i, (title, content) in enumerate(sections.items(), 1):
            # Section header
            lines.append(f"{i}️⃣ {title}")
            
            # Content (handle both strings and lists)
            if isinstance(content, list):
                for item in content:
                    lines.append(f"• {item}")
            else:
                lines.append(content)
            
            # Spacing between sections
            if include_spacing:
                lines.append("")
        
        return "\n".join(lines)


# Example usage for enforcement
def enforce_compliance_response(
    user_question: str,
    retrieved_documents: List[Dict[str, Any]],
    llm_response: str,
) -> str:
    """
    Enforce compliance-driven response format on LLM output.
    
    This function should be called AFTER RAG retrieval but BEFORE sending
    response to user. It validates and reformats the response.
    """
    
    # This is a template - actual implementation depends on question type
    # and retrieved document structure
    
    formatter = ComplianceResponseFormatter()
    
    # Determine question type
    if "policy" in user_question.lower() or "rule" in user_question.lower():
        # Policy question - use policy response format
        pass
    
    elif "entity" in user_question.lower() or "engage" in user_question.lower():
        # Entity/registry question - use registry format
        pass
    
    else:
        # Analytical question - use standard format
        pass
    
    return llm_response
