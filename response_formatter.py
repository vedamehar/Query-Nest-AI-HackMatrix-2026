"""
Structured Response Formatter: Enforces consistent, professional output format.
All responses follow strict structure: Status → Violations → Corrected Version → References.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class ComplianceStatus(Enum):
    APPROVED = "Approved ✓"
    CONDITIONALLY_ALLOWED = "Conditionally Allowed ⚠️"
    BLOCKED = "Blocked ✗"


class RiskLevel(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class Violation:
    issue: str
    document: str
    section: str
    clause: str
    risk_level: str
    recommendation: str


@dataclass
class StructuredResponse:
    compliance_status: str
    violations: List[Violation]
    corrected_version: Optional[str]
    policy_references: List[Dict[str, str]]
    audit_log_id: int
    
    def to_formatted_text(self) -> str:
        """Convert to professional formatted text."""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("COMPLIANCE REVIEW RESULT")
        lines.append("=" * 80)
        
        # Status
        lines.append("\n📋 COMPLIANCE STATUS")
        lines.append("-" * 80)
        lines.append(f"{self.compliance_status}")
        
        # Violations
        if self.violations:
            lines.append("\n⚠️ VIOLATIONS IDENTIFIED")
            lines.append("-" * 80)
            for i, v in enumerate(self.violations, 1):
                lines.append(f"\n{i}. {v.issue}")
                lines.append(f"   Document: {v.document}")
                lines.append(f"   Section: {v.section}")
                lines.append(f"   Clause: {v.clause}")
                lines.append(f"   Risk Level: {v.risk_level}")
                lines.append(f"   Recommendation: {v.recommendation}")
        else:
            lines.append("\n✓ No violations detected")
        
        # Corrected Version
        if self.corrected_version:
            lines.append("\n✅ CORRECTED VERSION")
            lines.append("-" * 80)
            lines.append(self.corrected_version)
        
        # References
        if self.policy_references:
            lines.append("\n📚 POLICY REFERENCES")
            lines.append("-" * 80)
            for ref in self.policy_references:
                lines.append(f"• {ref['name']} → {ref['path']}")
        
        # Audit
        lines.append("\n🔐 AUDIT INFORMATION")
        lines.append("-" * 80)
        lines.append(f"Audit Log ID: {self.audit_log_id}")
        
        lines.append("\n" + "=" * 80)
        
        return "\n".join(lines)


class ResponseFormatter:
    """Formats all responses with consistent structure."""
    
    @staticmethod
    def format_compliance_review(
        status: ComplianceStatus,
        violations: List[Violation] = None,
        corrected_version: str = None,
        references: List[Dict[str, str]] = None,
        audit_id: int = 0
    ) -> StructuredResponse:
        """Create structured compliance review response."""
        return StructuredResponse(
            compliance_status=status.value,
            violations=violations or [],
            corrected_version=corrected_version,
            policy_references=references or [],
            audit_log_id=audit_id
        )
    
    @staticmethod
    def format_registry_query(
        entity_name: str,
        status: str,
        details: Dict[str, Any],
        references: List[Dict[str, str]] = None,
        audit_id: int = 0
    ) -> Dict[str, Any]:
        """Format registry lookup response."""
        return {
            "entity": entity_name,
            "status": status,
            "details": details,
            "references": references or [],
            "audit_log_id": audit_id
        }
    
    @staticmethod
    def format_workflow_response(
        workflow_type: str,
        result: Dict[str, Any],
        references: List[Dict[str, str]] = None,
        audit_id: int = 0
    ) -> Dict[str, Any]:
        """Format workflow output."""
        return {
            "workflow": workflow_type,
            "result": result,
            "references": references or [],
            "audit_log_id": audit_id
        }
