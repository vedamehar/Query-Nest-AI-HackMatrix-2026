"""
CSV Registry Query: Direct structured lookups for entities.
Handles: Restricted_Entities_Registry, Approved_Alternatives_Registry
"""
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import config


class RegistryQueryEngine:
    """Direct SQL-like queries on CSV registries."""
    
    def __init__(self, restricted_csv: str, approved_csv: str):
        self.restricted_data = self._load_csv(restricted_csv)
        self.approved_data = self._load_csv(approved_csv)
        # Store entity names for fast lookup
        self.restricted_data_names = [row.get("EntityName", "") for row in self.restricted_data]
        self.approved_data_names = [row.get("EntityName", "") for row in self.approved_data]
    
    @staticmethod
    def _load_csv(path: str) -> List[Dict]:
        """Load CSV file into list of dicts."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
        except FileNotFoundError:
            return []
    
    def query_entity(self, entity_name: str) -> Tuple[str, Dict[str, any]]:
        """
        Query entity status.
        Returns: (status: "RESTRICTED" | "APPROVED" | "NOT_FOUND", details)
        """
        entity_lower = entity_name.lower()
        
        # Check restricted
        for row in self.restricted_data:
            if row.get("EntityName", "").lower() == entity_lower:
                return ("RESTRICTED", {
                    "entity_id": row.get("EntityID"),
                    "platform": row.get("Platform"),
                    "risk_score": row.get("RiskScore"),
                    "risk_reason": row.get("RiskReason"),
                    "monitoring_notes": row.get("MonitoringNotes"),
                    "status": row.get("RestrictionStatus")
                })
        
        # Check approved
        for row in self.approved_data:
            if row.get("EntityName", "").lower() == entity_lower:
                return ("APPROVED", {
                    "entity_id": row.get("EntityID"),
                    "platform": row.get("Platform"),
                    "category": row.get("Category"),
                    "safety_score": row.get("BrandSafetyScore"),
                    "usage_guideline": row.get("UsageGuideline"),
                    "approval_rationale": row.get("ApprovalRationale"),
                    "review_date": row.get("ReviewDate")
                })
        
        return ("NOT_FOUND", {})
    
    def search_by_category(self, category: str) -> List[Dict]:
        """Search approved entities by category."""
        results = []
        for row in self.approved_data:
            if category.lower() in row.get("Category", "").lower():
                results.append({
                    "name": row.get("EntityName"),
                    "category": row.get("Category"),
                    "platform": row.get("Platform"),
                    "safety_score": row.get("BrandSafetyScore"),
                    "usage_guideline": row.get("UsageGuideline")
                })
        return results
    
    def get_risk_reasons(self) -> List[str]:
        """Get all unique risk reasons."""
        reasons = set()
        for row in self.restricted_data:
            if row.get("RiskReason"):
                reasons.add(row.get("RiskReason"))
        return sorted(list(reasons))
    
    def is_entity_restricted(self, entity_name: str) -> bool:
        """Quick check if entity is restricted."""
        status, _ = self.query_entity(entity_name)
        return status == "RESTRICTED"
    
    def is_entity_approved(self, entity_name: str) -> bool:
        """Quick check if entity is approved."""
        status, _ = self.query_entity(entity_name)
        return status == "APPROVED"
    
    def get_approved_count(self) -> int:
        """Get count of approved entities."""
        return len(self.approved_data)
    
    def get_restricted_count(self) -> int:
        """Get count of restricted entities."""
        return len(self.restricted_data)
    
    def get_statistics(self) -> Dict:
        """Get registry statistics."""
        return {
            "approved_total": len(self.approved_data),
            "restricted_total": len(self.restricted_data),
            "risk_categories": len(set(r.get("RiskReason", "") for r in self.restricted_data if r.get("RiskReason"))),
            "platforms": len(set(r.get("Platform", "") for r in self.approved_data if r.get("Platform")))
        }
