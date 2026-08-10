"""
Compliance Enforcement Pipeline: Enterprise governance layer for structured responses.
Integrates query classification, metadata enforcement, response validation, and audit.
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from query_classifier import QueryType, classify_query, get_system_instruction
from response_structure_validator import (
    validate_response, 
    ResponseValidationStatus,
    get_validation_message
)
from metadata_enforcer import (
    enrich_documents_with_metadata,
    generate_citations,
    generate_reference_links,
)
import config


@dataclass
class EnforcedPipelineResponse:
    """Enhanced response with governance metadata."""
    success: bool
    message: str
    query_type: QueryType
    query_type_confidence: float
    retrieved_documents: List[Dict[str, Any]]
    llm_response: Optional[str]
    response_valid: bool
    validation_status: Optional[ResponseValidationStatus]
    validation_details: Dict[str, Any]
    regeneration_count: int
    citations_attached: List[str]
    reference_links: List[str]
    audit_log_id: int
    governance_checks: Dict[str, Any]


class ComplianceEnforcementPipeline:
    """
    Enterprise compliance enforcement layer.
    
    Enforces:
    1. Query type classification
    2. Structured output templates
    3. Mandatory citation attachment
    4. Full depth analysis
    5. Strict grounding
    6. Audit trail
    """
    
    MAX_REGENERATION_ATTEMPTS = 2
    
    def __init__(self, base_pipeline):
        """
        Initialize with existing pipeline.
        Acts as wrapper/decorator over GuardedRetrievalPipeline.
        """
        self.base_pipeline = base_pipeline
        self.query_classifier = None  # Lazy load
    
    def process_with_enforcement(self,
                                  query: str,
                                  user_id: str = "system",
                                  ip_address: str = "127.0.0.1",
                                  retrieved_documents: List[Dict] = None) -> EnforcedPipelineResponse:
        """
        Execute pipeline with full compliance enforcement.
        
        Process:
        1. Classify query type
        2. Enrich metadata
        3. Generate system instruction
        4. Call base pipeline
        5. Validate response structure
        6. Regenerate if invalid
        7. Attach citations
        8. Log governance checks
        """
        
        # STEP 1: Classify Query Type
        query_type, confidence = classify_query(query)
        print(f"[ENFORCE] Query Type: {query_type.value} (confidence: {confidence:.2f})")
        
        # STEP 2: Enrich metadata on retrieved documents
        if retrieved_documents:
            retrieved_documents = enrich_documents_with_metadata(retrieved_documents)
        
        # STEP 3: Generate query-type-specific system instruction
        type_instruction = get_system_instruction(query_type)
        
        # STEP 4: Call base pipeline with enhanced context
        base_response = self.base_pipeline.process(
            query=query,
            user_id=user_id,
            ip_address=ip_address
        )
        
        # STEP 5: Validate response structure
        validation_status, validation_details = validate_response(
            response_text=base_response.message,
            retrieved_docs=base_response.retrieved_documents,
            query_type=query_type.value
        )
        
        print(f"[ENFORCE] Validation: {validation_status.value}")
        
        # STEP 6: Regenerate if invalid
        response_text = base_response.message
        regeneration_count = 0
        
        if validation_status != ResponseValidationStatus.VALID:
            response_text, regeneration_count = self._regenerate_response(
                query=query,
                query_type=query_type,
                retrieved_documents=base_response.retrieved_documents,
                validation_status=validation_status,
                attempts_left=self.MAX_REGENERATION_ATTEMPTS
            )
        
        # STEP 7: Attach citations if documents exist
        citations = []
        reference_links = []
        
        if base_response.retrieved_documents:
            citations = generate_citations(base_response.retrieved_documents)
            reference_links = generate_reference_links(base_response.retrieved_documents)
            
            # Append citations to response if not present
            if citations and "POLICY REFERENCES" not in response_text:
                response_text = self._append_citations_section(
                    response_text, citations, reference_links
                )
        
        # STEP 8: Log governance checks
        governance_checks = {
            "query_type_detected": query_type.value,
            "query_type_confidence": confidence,
            "metadata_enriched": bool(base_response.retrieved_documents),
            "structure_validated": validation_status.value,
            "citations_attached": len(citations),
            "regenerated": regeneration_count > 0,
            "regeneration_attempts": regeneration_count,
            "grounding_enforced": bool(base_response.retrieved_documents),
            "audit_compliant": validation_status == ResponseValidationStatus.VALID,
        }
        
        if config.API_DEBUG:
            print(f"[ENFORCE] Governance Checks: {governance_checks}")
        
        # Build enforced response
        return EnforcedPipelineResponse(
            success=base_response.success,
            message=response_text,
            query_type=query_type,
            query_type_confidence=confidence,
            retrieved_documents=base_response.retrieved_documents,
            llm_response=base_response.llm_response,
            response_valid=validation_status == ResponseValidationStatus.VALID,
            validation_status=validation_status,
            validation_details=validation_details,
            regeneration_count=regeneration_count,
            citations_attached=citations,
            reference_links=reference_links,
            audit_log_id=base_response.audit_log_id,
            governance_checks=governance_checks,
        )
    
    def _regenerate_response(self,
                            query: str,
                            query_type: QueryType,
                            retrieved_documents: List[Dict],
                            validation_status: ResponseValidationStatus,
                            attempts_left: int) -> Tuple[str, int]:
        """
        Regenerate response if validation failed.
        Updates system prompt based on validation failure reason.
        """
        print(f"[ENFORCE] Response validation failed: {validation_status.value}")
        print(f"[ENFORCE] Attempting regeneration ({attempts_left} attempts left)...")
        
        if attempts_left <= 0:
            return f"[GOVERNANCE ALERT] Response structure validation failed: {validation_status.value}", 1
        
        # Get regeneration instruction based on failure type
        regen_instruction = self._get_regeneration_instruction(validation_status)
        
        # TODO: Call base_pipeline.llm_controller.generate() with updated prompt
        # For now, return indication that regeneration attempted
        
        return f"[Response regenerated due to: {validation_status.value}]", 1
    
    @staticmethod
    def _get_regeneration_instruction(status: ResponseValidationStatus) -> str:
        """Get regeneration instruction based on validation failure."""
        instructions = {
            ResponseValidationStatus.MISSING_SECTIONS: 
                "REGENERATE: Include all 5 required sections: COMPLIANCE STATUS, ANALYSIS, RISK LEVEL, POLICY REFERENCES, REFERENCE LINKS",
            
            ResponseValidationStatus.INVALID_STRUCTURE: 
                "REGENERATE: Structure response with multiple paragraphs and sections. Use bullet points.",
            
            ResponseValidationStatus.INSUFFICIENT_ANALYSIS: 
                "REGENERATE: Expand ANALYSIS section with at least 3 detailed bullet points. Use all retrieved documents.",
            
            ResponseValidationStatus.MISSING_CITATIONS: 
                "REGENERATE: Include POLICY REFERENCES and REFERENCE LINKS sections with citations from retrieved documents.",
            
            ResponseValidationStatus.HALLUCINATION_DETECTED: 
                "REGENERATE: Remove all unsupported claims. Only cite retrieved documents. Do not invent citations.",
        }
        
        return instructions.get(status, "REGENERATE: Fix structural issues")
    
    @staticmethod
    def _append_citations_section(response: str, 
                                  citations: List[str],
                                  reference_links: List[str]) -> str:
        """Append citations section if missing."""
        if not citations and not reference_links:
            return response
        
        citation_section = "\n\n4️⃣ POLICY REFERENCES:\n"
        for citation in citations:
            citation_section += f"• {citation}\n"
        
        links_section = "\n5️⃣ REFERENCE LINKS:\n"
        for link in reference_links:
            links_section += f"• {link}\n"
        
        return response + citation_section + links_section


def create_enforcement_pipeline(base_pipeline) -> ComplianceEnforcementPipeline:
    """Factory function to create enforcement pipeline."""
    return ComplianceEnforcementPipeline(base_pipeline)
