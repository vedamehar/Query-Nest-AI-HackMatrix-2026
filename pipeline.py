"""
GuardedRetrievalPipeline: Orchestrates compliance, retrieval, LLM, validation, and logging.
Core pipeline that ensures no LLM access without retrieved context.
Enforces proper RAG grounding - citations ONLY from metadata, never from LLM hallucinations.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from rules_engine import RuleEngine, ComplianceDecision
from vector_store import SemanticRetriever
from llm_interface import LLMController, ResponseValidator
from audit_logger import AuditLogger
from format_enforcer import StructuredFormatEnforcer
from registry_query_engine import RegistryQueryEngine
from rag_grounding_enforcer import (
    RAGResponseProcessor,
    ProperCitationGenerator,
    HallucinationDetector,
    StrictRAGPromptTemplate
)
import config


@dataclass
class PipelineResponse:
    success: bool
    message: str
    compliance_allowed: bool
    retrieved_documents: List[Dict[str, Any]]
    llm_response: Optional[str]
    response_valid: Optional[bool]
    validation_issues: List[str]
    audit_log_id: int


class GuardedRetrievalPipeline:
    """End-to-end query processing with all safety guards."""
    
    def __init__(self,
                 rule_engine: RuleEngine,
                 retriever: SemanticRetriever,
                 llm_controller: LLMController,
                 audit_logger: AuditLogger):
        self.rule_engine = rule_engine
        self.retriever = retriever
        self.llm_controller = llm_controller
        self.audit_logger = audit_logger
        self.response_validator = ResponseValidator()
        # Initialize registry query engine for direct CSV lookups
        self.registry_engine = RegistryQueryEngine(
            config.RESTRICTED_ENTITIES_CSV,
            config.APPROVED_ALTERNATIVES_CSV
        )
    
    def process(self,
                query: str,
                user_id: str = "system",
                ip_address: str = "127.0.0.1",
                video_id: Optional[str] = None,
                conversation_context: Optional[str] = None,
                session_id: Optional[str] = None) -> PipelineResponse:
        """
        Execute full pipeline:
        1. Rule engine check
        2. Retrieve documents (with optional video filtering)
        3. LLM reasoning
        4. Validate response
        5. Log everything
        
        NEW: Supports video_id for video-specific retrieval
        """
        
        retrieved_documents = []
        llm_response = None
        response_valid = None
        validation_issues = []
        
        print(f"\n[PIPELINE] Processing query: {query[:100]}...")
        
        print("[1/4] Checking compliance rules...")
        compliance_decision = self.rule_engine.check_compliance(query)
        
        if not compliance_decision.allowed:
            print(f"[BLOCKED] {compliance_decision.reason}")
            audit_entry = self.rule_engine.audit_log_entry(query, compliance_decision)
            log_id = self.audit_logger.log(
                query=query,
                compliance_decision=audit_entry,
                retrieved_documents=[],
                llm_response=None,
                response_valid=False,
                validation_issues=[compliance_decision.reason],
                user_id=user_id,
                ip_address=ip_address,
                session_id=session_id,
                context_used=bool(conversation_context)
            )
            
            suggestion_msg = f"\nSuggested alternatives: {', '.join(compliance_decision.suggestions)}" if compliance_decision.suggestions else ""
            return PipelineResponse(
                success=False,
                message=f"Query blocked: {compliance_decision.reason}{suggestion_msg}",
                compliance_allowed=False,
                retrieved_documents=[],
                llm_response=None,
                response_valid=False,
                validation_issues=[compliance_decision.reason],
                audit_log_id=log_id
            )
        
        print("[2/5] Checking entity registries (CSV lookup)...")
        # Try direct registry lookup first
        registry_status, registry_data = self._check_registry_first(query)
        
        if registry_status == "FOUND":
            print(f"[REGISTRY] Entity found in registry: {registry_data}")
            # Log and return registry data directly
            log_id = self.audit_logger.log(
                query=query,
                compliance_decision={"allowed": True},
                retrieved_documents=[],
                llm_response=self._format_registry_response(registry_data),
                response_valid=True,
                validation_issues=["Response from direct registry lookup"],
                user_id=user_id,
                ip_address=ip_address,
                session_id=session_id,
                context_used=bool(conversation_context)
            )
            
            return PipelineResponse(
                success=True,
                message=self._format_registry_response(registry_data),
                compliance_allowed=True,
                retrieved_documents=[],
                llm_response=self._format_registry_response(registry_data),
                response_valid=True,
                validation_issues=["Response from direct registry lookup"],
                audit_log_id=log_id
            )
        
        print("[3/5] Retrieving relevant documents...")
        # NEW: Support video-specific retrieval
        if video_id:
            print(f"[PIPELINE] Video-specific retrieval mode: {video_id}")
            retrieved_documents = self.retriever.retrieve(
                query,
                top_k=config.TOP_K_DOCUMENTS,
                similarity_threshold=config.SIMILARITY_THRESHOLD,
                video_id=video_id
            )
        else:
            retrieved_documents = self.retriever.retrieve(
                query,
                top_k=config.TOP_K_DOCUMENTS,
                similarity_threshold=config.SIMILARITY_THRESHOLD
            )
        
        if not retrieved_documents:
            print("[REFUSED] No relevant documents found")
            log_id = self.audit_logger.log(
                query=query,
                compliance_decision={"allowed": True},
                retrieved_documents=[],
                llm_response="No approved reference found in the current knowledge base.",
                response_valid=False,
                validation_issues=["No retrieved documents found"],
                user_id=user_id,
                ip_address=ip_address,
                session_id=session_id,
                context_used=bool(conversation_context)
            )
            
            return PipelineResponse(
                success=False,
                message="No approved reference found in the current knowledge base.",
                compliance_allowed=True,
                retrieved_documents=[],
                llm_response="No approved reference found in the current knowledge base.",
                response_valid=False,
                validation_issues=["No retrieved documents found"],
                audit_log_id=log_id
            )
        
        print(f"[RETRIEVED] {len(retrieved_documents)} document(s) found")
        
        # ✅ DEBUG: Print detailed retrieval information for verification
        self._debug_log_retrieved_documents(retrieved_documents)
        
        print("[3/6] Generating response with LLM...")
        context_text = self._format_context(retrieved_documents)
        
        # ✅ NEW: Build LLM message with conversation context
        llm_user_message = query
        if conversation_context:
            print(f"[3/6] Injecting {len(conversation_context)} chars of conversation context...")
            llm_user_message = f"""## Conversation Context
{conversation_context}

## Current Question
{query}"""
        
        # ✅ Use strict RAG prompt that prevents citation hallucination
        try:
            llm_response = self.llm_controller.generate(
                system_prompt=config.SYSTEM_PROMPT,  # Strict prompt (no citations)
                user_message=llm_user_message,
                context=context_text,
                max_tokens=config.LLM_MAX_TOKENS,
                retrieved_docs=retrieved_documents
            )
            print("[3/6] ✓ LLM response generated successfully")
        except RuntimeError as llm_error:
            print(f"[3/6] ✗ LLM generation failed: {str(llm_error)}")
            llm_response = f"System error during response generation: {str(llm_error)}"
            print(f"[3/6] Using fallback response")
        except Exception as llm_error:
            print(f"[3/6] ✗ Unexpected error during LLM generation: {str(llm_error)}")
            import traceback
            traceback.print_exc()
            llm_response = f"System error during response generation: {str(llm_error)}"
            print(f"[3/6] Using fallback response")
        
        # ✅ NEW STEP 4: RAG Grounding - Enforce proper citations
        print("[4/6] Enforcing RAG grounding (removing hallucinations)...")
        llm_response, grounding_report = RAGResponseProcessor.process_response(
            llm_response,
            retrieved_documents
        )
        
        if grounding_report["has_hallucinations"]:
            print(f"[RAG] ⚠️  Removed hallucinated citations: {grounding_report['hallucinated_patterns']}")
            if grounding_report["enforcement_applied"]:
                print(f"[RAG] ✓ Enforcement applied")
        
        print(f"[RAG] ✓ Proper citations attached: {grounding_report['citations_attached']}")
        
        print("[5/6] Validating response...")
        validation_result = self.response_validator.validate(
            llm_response,
            retrieved_documents,
            self.llm_controller
        )
        response_valid = validation_result["is_valid"]
        validation_issues = validation_result.get("issues", [])
        
        if not response_valid:
            print(f"[WARNING] Response failed validation: {', '.join(validation_issues)}")
        
        # Step 6: Format Enforcement - Ensure structured compliance format
        print("[6/6] Enforcing structured compliance format...")
        format_check = StructuredFormatEnforcer.check_format_compliance(llm_response)
        if not format_check["is_compliant"]:
            print(f"[FORMAT] Enforcing structure - issues: {format_check['issues']}")
            llm_response = StructuredFormatEnforcer.enforce_format(llm_response)
            validation_issues.append("Response reformatted to structured compliance format")
        
        # Logging: Record validated response with proper citations
        print("[LOGGING] Recording to audit trail...")
        log_id = self.audit_logger.log(
            query=query,
            compliance_decision={"allowed": True},
            retrieved_documents=retrieved_documents,
            llm_response=llm_response,
            response_valid=response_valid,
            validation_issues=validation_issues,
            user_id=user_id,
            ip_address=ip_address,
            session_id=session_id,
            context_used=bool(conversation_context)
        )
        
        return PipelineResponse(
            success=response_valid,
            message=llm_response,
            compliance_allowed=True,
            retrieved_documents=retrieved_documents,
            llm_response=llm_response,
            response_valid=response_valid,
            validation_issues=validation_issues,
            audit_log_id=log_id
        )
    
    def _check_registry_first(self, query: str) -> tuple:
        """
        Check registries FIRST before vector search.
        Returns: (status, data) where status is "FOUND" or "NOT_FOUND"
        """
        # Extract entity names from query
        query_lower = query.lower()
        
        # Search for entity mentions in restricted registry
        for entity_name in self.registry_engine.restricted_data_names:
            if entity_name.lower() in query_lower:
                status, data = self.registry_engine.query_entity(entity_name)
                if status == "RESTRICTED":
                    return ("FOUND", {"entity": entity_name, "status": "RESTRICTED", "data": data})
        
        # Search for entity mentions in approved registry
        for entity_name in self.registry_engine.approved_data_names:
            if entity_name.lower() in query_lower:
                status, data = self.registry_engine.query_entity(entity_name)
                if status == "APPROVED":
                    return ("FOUND", {"entity": entity_name, "status": "APPROVED", "data": data})
        
        return ("NOT_FOUND", {})
    
    def _format_registry_response(self, registry_data: Dict[str, Any]) -> str:
        """Format registry data into structured compliance response."""
        entity = registry_data.get("entity", "Unknown")
        status = registry_data.get("status", "NOT_FOUND")
        data = registry_data.get("data", {})
        
        if status == "RESTRICTED":
            return f"""1️⃣ COMPLIANCE STATUS
Blocked

2️⃣ VIOLATIONS IDENTIFIED
• Restricted entity mentioned: "{entity}"
  Why it violates: Restricted_Entities_Registry.csv – Entity is blocked for compliance reasons

3️⃣ RISK LEVEL
{data.get('risk_score', 'High')}

4️⃣ REQUIRED CORRECTIONS
• Do not mention or promote this entity
• Use approved alternatives instead
• Review compliance constraints for this entity

5️⃣ FULLY REWRITTEN COMPLIANT VERSION
This entity is restricted and cannot be promoted or discussed in compliance-bound communications.

6️⃣ POLICY REFERENCES
Restricted_Entities_Registry.csv — Entity: {entity}

7️⃣ REFERENCE LINKS
Restricted_Entities_Registry.csv → /docs/registries/Restricted_Entities"""
        
        else:  # APPROVED
            return f"""1️⃣ COMPLIANCE STATUS
Approved

2️⃣ VIOLATIONS IDENTIFIED
None

3️⃣ RISK LEVEL
Low

5️⃣ FULLY REWRITTEN COMPLIANT VERSION
{entity} is approved for marketing and promotional use. Review the guidelines below for compliance requirements.

6️⃣ POLICY REFERENCES
Approved_Alternatives_Registry.csv — Entity: {entity}
Guidelines: {data.get('guidelines', 'Standard compliance applies')}

7️⃣ REFERENCE LINKS
Approved_Alternatives_Registry.csv → /docs/registries/Approved_Alternatives"""
    
    @staticmethod
    def _format_context(documents: List[Dict[str, Any]]) -> str:
        """Format retrieved documents as context."""
        context_parts = []
        for doc in documents:
            source = f"[{doc.get('doc_name')}:{doc.get('chunk_id')}]"
            text = doc.get('text', '')
            similarity = doc.get('similarity_score', 0)
            context_parts.append(f"{source} (relevance: {similarity:.2f})\n{text}\n")
        
        return "\n---\n".join(context_parts)
    
    @staticmethod
    def _add_references_and_links(response: str, documents: List[Dict[str, Any]]) -> str:
        """Add references and links section to response."""
        if not documents:
            return response
        
        # Extract unique document names
        doc_names = set()
        for doc in documents:
            doc_name = doc.get('doc_name', '')
            if doc_name:
                doc_names.add(doc_name)
        
        if not doc_names:
            return response
        
        # Check if response already has reference sections
        if "6️⃣" in response or "POLICY REFERENCES" in response:
            # Response already has references, don't add duplicates
            return response
        
        # Build references section with clickable links
        references = []
        
        for doc_name in sorted(doc_names):
            # Create Markdown link format [DocumentName](/docs/DocumentName)
            doc_path = doc_name.replace('.csv', '').replace('.md', '').replace('.txt', '')
            link = f"[{doc_name}](/docs/{doc_path})"
            references.append(link)
        
        # Append sections to response
        # Section 6: Policy References (with clickable links)
        ref_section = "\n\n## 6️⃣ POLICY REFERENCES\n\n" + "\n".join(f"- {ref}" for ref in references)
        
        # Section 7: Reference Links (alternative format for clarity)
        link_section = "\n\n## 7️⃣ REFERENCE LINKS\n\n" + "\n".join(f"- [{doc_name}](/docs/{doc_name.replace('.csv', '').replace('.md', '').replace('.txt', '')})" for doc_name in sorted(doc_names))
        
        return response + ref_section + link_section
    
    @staticmethod
    def _debug_log_retrieved_documents(documents: List[Dict[str, Any]]) -> None:
        """
        Print detailed debug information about retrieved documents.
        Helps verify that newly uploaded documents are being retrieved.
        Only prints if config.API_DEBUG is enabled.
        """
        if not hasattr(config, 'API_DEBUG') or not config.API_DEBUG:
            return
        
        print("\n" + "="*70)
        print("[DEBUG] RETRIEVED DOCUMENTS VERIFICATION")
        print("="*70)
        
        if not documents:
            print("⚠️  No documents retrieved")
            print("="*70 + "\n")
            return
        
        print(f"\n📊 Total documents retrieved: {len(documents)}\n")
        
        for i, doc in enumerate(documents, 1):
            # Safe dictionary access with defaults
            source_file = doc.get("doc_name", "Unknown")
            document_id = doc.get("document_id", "N/A")
            chunk_id = doc.get("chunk_id", "Unknown")
            similarity_score = doc.get("similarity_score", "N/A")
            
            # Format similarity score
            if isinstance(similarity_score, (int, float)):
                similarity_str = f"{float(similarity_score):.4f}"
            else:
                similarity_str = str(similarity_score)
            
            print(f"{i}. 📄 Retrieved Document")
            print(f"   Source File: {source_file}")
            print(f"   Document ID: {document_id}")
            print(f"   Chunk ID: {chunk_id}")
            print(f"   Similarity Score: {similarity_str}")
            
            # Print metadata dictionary
            if "metadata" in doc:
                print(f"   Metadata: {doc.get('metadata')}")
            else:
                # Show all other fields as metadata
                metadata_dict = {k: v for k, v in doc.items() 
                               if k not in ["text", "doc_name", "document_id", "chunk_id", "similarity_score"]}
                if metadata_dict:
                    print(f"   Metadata: {metadata_dict}")
            
            # Show text snippet
            text_preview = doc.get("text", "")[:100]
            if len(text_preview) >= 100:
                text_preview += "..."
            print(f"   Text Preview: {text_preview}")
            print()
        
        print("="*70)
        print("[DEBUG] ✅ Document retrieval verified\n")
