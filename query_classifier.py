"""
Query Classifier: Detects query type for behavioral routing.
Enables different response strategies based on query intent.
"""
from typing import Tuple
from enum import Enum
import re


class QueryType(Enum):
    """Four canonical query types for compliance routing."""
    POLICY_ANALYTICAL = "POLICY_ANALYTICAL"
    DRAFT_REVIEW = "DRAFT_REVIEW"
    ENTITY_VALIDATION = "ENTITY_VALIDATION"
    WORKFLOW_ASSISTANCE = "WORKFLOW_ASSISTANCE"


class QueryClassifier:
    """
    Lightweight classifier that detects query intent.
    Routes to appropriate response handler.
    """
    
    def __init__(self):
        """Initialize classifier with pattern sets."""
        # Draft review indicators
        self.draft_review_patterns = [
            r"is this.*compliant",
            r"review this",
            r"rewrite.*content",
            r"check.*compliance",
            r"is this post",
            r"fix this",
            r"correct this",
            r"edit.*policy",
            r"draft.*review",
            r"violations.*found",
            r"content.*rewrite",
        ]
        
        # Entity validation indicators
        self.entity_patterns = [
            r"is.*approved",
            r"is.*allowed",
            r"can we use",
            r"is.*permitted",
            r"is.*restricted",
            r"entity.*validation",
            r"approval.*status",
            r"registry.*check",
            r"blocked.*entity",
            r"approved.*alternative",
        ]
        
        # Workflow assistance indicators
        self.workflow_patterns = [
            r"draft.*post",
            r"draft.*email",
            r"draft.*statement",
            r"draft.*response",
            r"create.*content",
            r"write.*compliant",
            r"compose.*message",
            r"generate.*template",
            r"workflow.*assistance",
            r"how.*draft",
            r"help.*write",
        ]
        
        # Policy/analytical indicators
        self.policy_patterns = [
            r"what.*risk",
            r"what.*conflict",
            r"analysis",
            r"interpret.*policy",
            r"explain.*rule",
            r"why.*prohibited",
            r"governance",
            r"compliance.*question",
            r"what happens if",
            r"implications.*of",
        ]
    
    def classify(self, query: str) -> Tuple[QueryType, float]:
        """
        Classify query into one of four types.
        
        Returns:
            (QueryType, confidence_score)
        """
        query_lower = query.lower().strip()
        
        # Check draft review first (most specific)
        score = self._match_patterns(query_lower, self.draft_review_patterns)
        if score >= 0.7:
            return QueryType.DRAFT_REVIEW, score
        
        # Check entity validation
        score = self._match_patterns(query_lower, self.entity_patterns)
        if score >= 0.7:
            return QueryType.ENTITY_VALIDATION, score
        
        # Check workflow assistance
        score = self._match_patterns(query_lower, self.workflow_patterns)
        if score >= 0.7:
            return QueryType.WORKFLOW_ASSISTANCE, score
        
        # Check policy/analytical
        score = self._match_patterns(query_lower, self.policy_patterns)
        if score >= 0.7:
            return QueryType.POLICY_ANALYTICAL, score
        
        # Default: treat as policy/analytical (safest default)
        return QueryType.POLICY_ANALYTICAL, 0.5
    
    @staticmethod
    def _match_patterns(text: str, patterns: list) -> float:
        """
        Calculate match score against pattern list.
        Returns confidence 0.0-1.0
        """
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        
        if not patterns:
            return 0.0
        
        return min(1.0, matches / len(patterns))
    
    def get_system_instruction(self, query_type: QueryType) -> str:
        """
        Get query-type-specific system instruction.
        Injected into LLM prompt.
        """
        instructions = {
            QueryType.POLICY_ANALYTICAL: """
QUERY TYPE: POLICY / ANALYTICAL

Do NOT generate a rewritten version.
Focus ONLY on:
1. Compliance analysis
2. Risk implications  
3. Required corrective actions (if applicable)

Include citations and policy references.
""",
            
            QueryType.DRAFT_REVIEW: """
QUERY TYPE: DRAFT REVIEW / CONTENT REWRITE

Provide:
1. Violations identified
2. Risk analysis
3. Corrected rewritten version
4. Policy references

Include all violations found with supporting citations.
""",
            
            QueryType.ENTITY_VALIDATION: """
QUERY TYPE: ENTITY VALIDATION

Answer with:
1. Approval status (Approved/Restricted/Unknown)
2. Registry citation
3. Approved alternatives (if restricted)
4. Relevant policy context

Be direct and specific about approval status.
""",
            
            QueryType.WORKFLOW_ASSISTANCE: """
QUERY TYPE: WORKFLOW ASSISTANCE

Provide:
1. Operational steps
2. Compliance requirements
3. Templates/examples
4. Policy guardrails

Ensure output is actionable and compliant.
""",
        }
        
        return instructions.get(query_type, "")


# Singleton instance
_classifier = QueryClassifier()


def classify_query(query: str) -> Tuple[QueryType, float]:
    """Public function to classify query."""
    return _classifier.classify(query)


def get_system_instruction(query_type: QueryType) -> str:
    """Public function to get system instruction."""
    return _classifier.get_system_instruction(query_type)
