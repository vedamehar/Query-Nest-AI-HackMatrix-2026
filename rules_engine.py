"""
Rules engine: Compliance checking using CSV registries.
Blocks queries referencing restricted entities before LLM reasoning.
"""
import csv
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class ComplianceDecision:
    allowed: bool
    reason: str
    restricted_entities: List[str]
    suggestions: List[str]
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW


class RegistryLoader:
    """Load and manage compliance registries."""
    
    @staticmethod
    def load_restricted_entities(csv_path: str) -> Dict[str, Dict]:
        """Load restricted entities registry."""
        entities = {}
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entity_name = row.get("EntityName", "").lower()
                    entities[entity_name] = {
                        "entity_id": row.get("EntityID"),
                        "platform": row.get("Platform"),
                        "risk_score": int(row.get("RiskScore", 0)),
                        "risk_reason": row.get("RiskReason"),
                        "status": row.get("RestrictionStatus"),
                    }
        except FileNotFoundError:
            print(f"Warning: Registry not found at {csv_path}")
        
        return entities
    
    @staticmethod
    def load_approved_entities(csv_path: str) -> Dict[str, Dict]:
        """Load approved entities registry."""
        entities = {}
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entity_name = row.get("EntityName", "").lower()
                    entities[entity_name] = {
                        "entity_id": row.get("EntityID"),
                        "platform": row.get("Platform"),
                        "category": row.get("Category"),
                        "safety_score": int(row.get("BrandSafetyScore", 0)),
                        "usage_guideline": row.get("UsageGuideline"),
                    }
        except FileNotFoundError:
            print(f"Warning: Registry not found at {csv_path}")
        
        return entities


class RuleEngine:
    """Stateless rule enforcement for compliance."""
    
    def __init__(self, restricted_csv: str, approved_csv: str):
        self.loader = RegistryLoader()
        self.restricted_entities = self.loader.load_restricted_entities(restricted_csv)
        self.approved_entities = self.loader.load_approved_entities(approved_csv)
    
    def extract_entities(self, text: str) -> List[str]:
        """Extract potential entity names from query."""
        words = text.lower().split()
        
        potential_entities = []
        for entity_name in self.restricted_entities.keys():
            if entity_name in text.lower():
                potential_entities.append(entity_name)
        
        for entity_name in self.approved_entities.keys():
            if entity_name in text.lower():
                potential_entities.append(entity_name)
        
        return potential_entities
    
    def check_compliance(self, query: str) -> ComplianceDecision:
        """Check if query violates compliance rules."""
        query_lower = query.lower()
        found_restricted = []
        suggestions = []
        max_risk_score = 0
        
        for entity_name, entity_info in self.restricted_entities.items():
            if entity_name in query_lower:
                found_restricted.append(entity_name)
                max_risk_score = max(max_risk_score, entity_info.get("risk_score", 0))
        
        if found_restricted:
            severity = "CRITICAL" if max_risk_score >= 9 else "HIGH" if max_risk_score >= 7 else "MEDIUM"
            
            for entity in found_restricted:
                for approved_entity in self.approved_entities.keys():
                    if self.approved_entities[approved_entity].get("category") == self.restricted_entities[entity].get("risk_reason"):
                        suggestions.append(approved_entity)
            
            return ComplianceDecision(
                allowed=False,
                reason=f"Query references restricted entity: {', '.join(found_restricted)}",
                restricted_entities=found_restricted,
                suggestions=list(set(suggestions))[:3],
                severity=severity
            )
        
        return ComplianceDecision(
            allowed=True,
            reason="Query passed compliance check",
            restricted_entities=[],
            suggestions=[],
            severity="NONE"
        )
    
    def audit_log_entry(self, query: str, decision: ComplianceDecision) -> Dict[str, Any]:
        """Create audit log entry for compliance decision."""
        return {
            "query": query,
            "decision": "ALLOWED" if decision.allowed else "BLOCKED",
            "reason": decision.reason,
            "restricted_entities": decision.restricted_entities,
            "severity": decision.severity,
            "suggestions": decision.suggestions
        }
