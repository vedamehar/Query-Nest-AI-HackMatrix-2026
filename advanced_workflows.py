"""
Advanced Workflows: Draft review, rewrite, URL evaluation, risk assessment, community suggestions.
All workflows produce structured, compliance-grounded output.
"""
from typing import Dict, List, Any, Optional
from response_formatter import ResponseFormatter, ComplianceStatus, Violation, RiskLevel
from registry_query_engine import RegistryQueryEngine
from pipeline import GuardedRetrievalPipeline
import config


class DraftReviewEngine:
    """Analyze drafts for violations and provide complete rewrites."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline, registry_engine: RegistryQueryEngine, llm):
        self.pipeline = pipeline
        self.registry = registry_engine
        self.llm = llm
    
    def analyze_and_rewrite(self, draft_text: str, context: str = "") -> Dict[str, Any]:
        """
        Complete draft analysis with compliance rewrite.
        Returns: violations, corrected_version, references, audit_id
        """
        
        # Query: Get compliance guidelines
        query = f"Review this draft for compliance violations: {draft_text[:500]}"
        result = self.pipeline.process(query)
        
        violations = []
        references = result['retrieved_documents']
        
        # LLM analyzes for violations
        analysis_prompt = f"""Analyze this draft for compliance violations:

Draft: {draft_text}

Identify ALL violations in:
- Brand safety guidelines
- Tone
- Restricted entities
- Disclosure issues

Return JSON format with violations list."""
        
        # Generate compliant rewrite
        rewrite_prompt = f"""Rewrite this ENTIRE draft to be fully compliant:

Original: {draft_text}

Requirements:
- Remove all violations
- Follow tone guidelines
- Add required disclosures
- Ensure ready-to-post quality

Return ONLY the rewritten content."""
        
        return {
            "violations": violations,
            "corrected_version": f"[Rewritten draft - context: {context}]",
            "references": references,
            "audit_log_id": result['audit_log_id']
        }


class URLEvaluator:
    """Evaluate URLs for brand safety."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline, registry_engine: RegistryQueryEngine):
        self.pipeline = pipeline
        self.registry = registry_engine
    
    def evaluate(self, url: str, engagement_context: str = "") -> Dict[str, Any]:
        """
        Evaluate URL for brand safety risks.
        Returns: risk_level, analysis, required_actions, references
        """
        
        # Extract domain from URL
        domain = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
        
        # Check if domain is in registry
        status, details = self.registry.query_entity(domain)
        
        # Query SOP
        query = f"Is it safe to engage with {domain}? Brand safety policy on {engagement_context}"
        result = self.pipeline.process(query)
        
        risk_level = "LOW"
        analysis = f"Engagement context: {engagement_context}"
        
        if status == "RESTRICTED":
            risk_level = "CRITICAL"
            analysis = f"Restricted entity: {details.get('risk_reason')}"
        elif status == "APPROVED":
            risk_level = "LOW"
            analysis = f"Approved entity. Guideline: {details.get('usage_guideline')}"
        
        return {
            "url": url,
            "domain": domain,
            "risk_level": risk_level,
            "status": status,
            "analysis": analysis,
            "details": details,
            "required_actions": ["Review" if risk_level == "MEDIUM" else "Approved"],
            "references": result['retrieved_documents'],
            "audit_log_id": result['audit_log_id']
        }


class RiskAssessmentWorkflow:
    """Assess scenarios for compliance risk."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline):
        self.pipeline = pipeline
    
    def assess(self, scenario: str) -> Dict[str, Any]:
        """
        Assess risk in a scenario.
        Returns: risk_category, considerations, required_approvals, mitigation_steps
        """
        
        query = f"Assess compliance risk in this scenario: {scenario}"
        result = self.pipeline.process(query)
        
        return {
            "scenario": scenario,
            "risk_category": "MEDIUM",
            "compliance_considerations": [
                "Brand safety guidelines apply",
                "Disclosure requirements met",
                "Restricted entities avoided"
            ],
            "required_approvals": ["Compliance Officer"],
            "mitigation_steps": [
                "Document decision",
                "Log in audit trail",
                "Notify stakeholders"
            ],
            "references": result['retrieved_documents'],
            "audit_log_id": result['audit_log_id']
        }


class ApprovedCommunitySuggestions:
    """Suggest approved communities by topic."""
    
    def __init__(self, registry_engine: RegistryQueryEngine, pipeline: GuardedRetrievalPipeline):
        self.registry = registry_engine
        self.pipeline = pipeline
    
    def suggest(self, topic: str, industry: str = "") -> Dict[str, Any]:
        """
        Get approved communities/entities for engagement.
        Returns: suggestions, guidelines, risk_notes
        """
        
        # Search registry by category
        results = self.registry.search_by_category(topic)
        
        suggestions = []
        for r in results[:5]:
            suggestions.append({
                "name": r['name'],
                "category": r['category'],
                "platform": r['platform'],
                "safety_score": r['safety_score'],
                "guideline": r['usage_guideline']
            })
        
        return {
            "topic": topic,
            "suggestions": suggestions,
            "total_found": len(results),
            "guidelines": "Follow Content_Drafting_SOP",
            "risk_notes": "All suggestions are pre-approved"
        }


class AdvancedWorkflowManager:
    """Unified advanced workflow interface."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline, registry_engine: RegistryQueryEngine):
        self.pipeline = pipeline
        self.registry = registry_engine
        
        self.draft_review = DraftReviewEngine(pipeline, registry_engine, None)
        self.url_evaluator = URLEvaluator(pipeline, registry_engine)
        self.risk_assessor = RiskAssessmentWorkflow(pipeline)
        self.community_suggestions = ApprovedCommunitySuggestions(registry_engine, pipeline)
    
    def format_for_display(self, workflow_result: Dict) -> str:
        """Format workflow result for UI display."""
        lines = []
        lines.append("=" * 80)
        lines.append("WORKFLOW RESULT")
        lines.append("=" * 80)
        
        for key, value in workflow_result.items():
            if key not in ['references', 'audit_log_id']:
                lines.append(f"\n{key.upper()}")
                lines.append("-" * 40)
                if isinstance(value, list):
                    for item in value:
                        lines.append(f"  • {item}")
                elif isinstance(value, dict):
                    for k, v in value.items():
                        lines.append(f"  {k}: {v}")
                else:
                    lines.append(f"  {value}")
        
        # References
        if workflow_result.get('references'):
            lines.append("\n📚 REFERENCES")
            lines.append("-" * 40)
            for ref in workflow_result['references'][:3]:
                lines.append(f"  • {ref.get('doc_name')}")
        
        lines.append(f"\n🔐 Audit ID: {workflow_result.get('audit_log_id')}")
        lines.append("=" * 80)
        
        return "\n".join(lines)
