"""
Productivity workflows: Specialized tools aligned with SOPs.
All features pass through the compliance pipeline.
"""
from typing import Dict, List, Any, Optional
from pipeline import GuardedRetrievalPipeline


class DraftWorkflow:
    """Compliant Reddit response drafting based on Content_Drafting_SOP."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline):
        self.pipeline = pipeline
    
    def draft_response(self,
                      topic: str,
                      subreddit: str,
                      user_id: str = "system") -> Dict[str, Any]:
        """Draft a compliant Reddit response."""
        
        query = f"How should I respond about '{topic}' on r/{subreddit}? Follow Content_Drafting_SOP guidelines."
        result = self.pipeline.process(query, user_id=user_id)
        
        return {
            "success": result.success,
            "topic": topic,
            "subreddit": subreddit,
            "draft": result.message,
            "compliance_check": result.compliance_allowed,
            "citations": [doc.get("doc_name") for doc in result.retrieved_documents],
            "audit_log_id": result.audit_log_id
        }


class URLEvaluator:
    """Policy-context URL evaluation based on URL_Evaluation_SOP."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline):
        self.pipeline = pipeline
    
    def evaluate_url(self,
                    url: str,
                    context: str = "",
                    user_id: str = "system") -> Dict[str, Any]:
        """Evaluate if a URL is safe to engage with."""
        
        query = f"Is this URL safe to engage with in our brand context: {url}? Context: {context}. Reference URL_Evaluation_SOP."
        result = self.pipeline.process(query, user_id=user_id)
        
        return {
            "success": result.success,
            "url": url,
            "is_safe": "safe" in result.message.lower() and result.compliance_allowed,
            "reasoning": result.message,
            "compliance_check": result.compliance_allowed,
            "audit_log_id": result.audit_log_id
        }


class TranscriptSummarizer:
    """Transcript processing and summarization based on Transcript_Processing_SOP."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline):
        self.pipeline = pipeline
    
    def summarize_transcript(self,
                            transcript: str,
                            user_id: str = "system") -> Dict[str, Any]:
        """Summarize a transcript with brand safety considerations."""
        
        snippet = transcript[:500] + "..." if len(transcript) > 500 else transcript
        query = f"Summarize this transcript following Transcript_Processing_SOP: {snippet}"
        result = self.pipeline.process(query, user_id=user_id)
        
        return {
            "success": result.success,
            "summary": result.message,
            "compliance_check": result.compliance_allowed,
            "referenced_policies": [doc.get("doc_name") for doc in result.retrieved_documents],
            "audit_log_id": result.audit_log_id
        }


class RiskAdvisor:
    """Risk-aware recommendations based on Social_Risk_Assessment_SOP."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline):
        self.pipeline = pipeline
    
    def assess_risk(self,
                   scenario: str,
                   user_id: str = "system") -> Dict[str, Any]:
        """Provide risk assessment and recommendations."""
        
        query = f"Assess the risk in this scenario and recommend actions per Social_Risk_Assessment_SOP: {scenario}"
        result = self.pipeline.process(query, user_id=user_id)
        
        return {
            "success": result.success,
            "scenario": scenario,
            "risk_assessment": result.message,
            "compliance_check": result.compliance_allowed,
            "sources": [doc.get("doc_name") for doc in result.retrieved_documents],
            "audit_log_id": result.audit_log_id
        }


class WorkflowManager:
    """Unified workflow interface."""
    
    def __init__(self, pipeline: GuardedRetrievalPipeline):
        self.pipeline = pipeline
        self.draft = DraftWorkflow(pipeline)
        self.url_evaluator = URLEvaluator(pipeline)
        self.transcript_summarizer = TranscriptSummarizer(pipeline)
        self.risk_advisor = RiskAdvisor(pipeline)
