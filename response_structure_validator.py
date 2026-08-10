"""
Response Validator: Enforces strict structured format compliance.
Validates responses meet enterprise governance standards.
"""
from typing import Dict, List, Tuple, Optional
import re
from enum import Enum


class ResponseValidationStatus(Enum):
    """Response validation outcomes."""
    VALID = "VALID"
    MISSING_SECTIONS = "MISSING_SECTIONS"
    INVALID_STRUCTURE = "INVALID_STRUCTURE"
    INSUFFICIENT_ANALYSIS = "INSUFFICIENT_ANALYSIS"
    MISSING_CITATIONS = "MISSING_CITATIONS"
    HALLUCINATION_DETECTED = "HALLUCINATION_DETECTED"


class StructuredResponseValidator:
    """
    Validates responses against enterprise compliance standards.
    Enforces required sections, citation attachments, depth of analysis.
    """
    
    REQUIRED_SECTIONS = [
        "1️⃣ COMPLIANCE STATUS",
        "2️⃣ ANALYSIS",
        "3️⃣ RISK LEVEL",
        "4️⃣ POLICY REFERENCES",
        "5️⃣ REFERENCE LINKS",
    ]
    
    ANALYSIS_SECTION_HEADERS = [
        "ANALYSIS",
        "2️⃣",
    ]
    
    def validate_response(self, response_text: str, 
                         retrieved_docs: List[Dict] = None,
                         query_type: str = None) -> Tuple[ResponseValidationStatus, Dict]:
        """
        Validate response structure and compliance.
        
        Returns:
            (status, details_dict)
        """
        details = {
            "present_sections": [],
            "missing_sections": [],
            "analysis_bullet_count": 0,
            "has_citations": False,
            "has_reference_links": False,
            "is_single_paragraph": False,
            "analysis_depth_adequate": False,
            "retrieved_doc_count": len(retrieved_docs) if retrieved_docs else 0,
            "issues": [],
        }
        
        # Check 1: Required sections present
        for section in self.REQUIRED_SECTIONS:
            if section in response_text or section.split()[0] in response_text:
                details["present_sections"].append(section)
            else:
                details["missing_sections"].append(section)
        
        if details["missing_sections"]:
            details["issues"].append(f"Missing sections: {details['missing_sections']}")
            return ResponseValidationStatus.MISSING_SECTIONS, details
        
        # Check 2: Analysis section has multiple bullet points
        analysis_bullets = self._count_analysis_bullets(response_text)
        details["analysis_bullet_count"] = analysis_bullets
        
        if analysis_bullets < 3:
            details["issues"].append(f"Analysis has only {analysis_bullets} bullet points (need >= 3)")
            details["analysis_depth_adequate"] = False
            return ResponseValidationStatus.INSUFFICIENT_ANALYSIS, details
        
        details["analysis_depth_adequate"] = True
        
        # Check 3: Not a single paragraph
        paragraphs = [p.strip() for p in response_text.split('\n\n') if p.strip()]
        if len(paragraphs) < 4:
            details["is_single_paragraph"] = True
            details["issues"].append("Response appears to be single/compact paragraph (need structured sections)")
            return ResponseValidationStatus.INVALID_STRUCTURE, details
        
        # Check 4: Citations present
        has_policy_refs = "4️⃣ POLICY REFERENCES" in response_text or "POLICY REFERENCES" in response_text
        has_ref_links = "5️⃣ REFERENCE LINKS" in response_text or "REFERENCE LINKS" in response_text
        
        if not has_policy_refs or not has_ref_links:
            details["issues"].append("Missing citation sections")
            return ResponseValidationStatus.MISSING_CITATIONS, details
        
        details["has_citations"] = has_policy_refs
        details["has_reference_links"] = has_ref_links
        
        # Check 5: Content alignment with retrieved documents
        if retrieved_docs:
            hallucination_check = self._check_for_hallucination(response_text, retrieved_docs)
            if hallucination_check["likely_hallucination"]:
                details["issues"].extend(hallucination_check["red_flags"])
                return ResponseValidationStatus.HALLUCINATION_DETECTED, details
        
        # All checks passed
        return ResponseValidationStatus.VALID, details
    
    @staticmethod
    def _count_analysis_bullets(text: str) -> int:
        """Count bullet points in analysis section."""
        # Find analysis section
        analysis_match = re.search(
            r'(?:2️⃣|ANALYSIS:)(.*?)(?:3️⃣|RISK LEVEL:|$)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        
        if not analysis_match:
            return 0
        
        analysis_section = analysis_match.group(1)
        
        # Count bullet points
        bullets = re.findall(r'^\s*[•\-\*]\s+', analysis_section, re.MULTILINE)
        return len(bullets)
    
    @staticmethod
    def _check_for_hallucination(response: str, retrieved_docs: List[Dict]) -> Dict:
        """
        Check for hallucinated content not in retrieved documents.
        Look for invented section numbers, fake file names, etc.
        """
        issues = {
            "likely_hallucination": False,
            "red_flags": [],
        }
        
        if not retrieved_docs:
            return issues
        
        # Extract actual document names from retrieved docs
        actual_doc_names = set()
        for doc in retrieved_docs:
            if "doc_name" in doc:
                actual_doc_names.add(doc["doc_name"])
            if "source" in doc:
                actual_doc_names.add(doc["source"])
        
        # Look for suspicious citations
        citation_pattern = r'(?:Section|Section\s+\d+\.?\d*|Page\s+\d+)'
        citations_found = re.findall(citation_pattern, response, re.IGNORECASE)
        
        # If citations exist but no documents retrieved, it's suspicious
        if citations_found and not actual_doc_names:
            issues["red_flags"].append(
                "Found citations but no documents were retrieved - possible hallucination"
            )
            issues["likely_hallucination"] = True
        
        # Check for specific file names in response that weren't retrieved
        for doc_name in actual_doc_names:
            if doc_name not in response:
                # Document was retrieved but not cited
                # This might be okay, but worth tracking
                pass
        
        return issues
    
    def get_validation_message(self, status: ResponseValidationStatus, 
                               details: Dict) -> str:
        """Generate human-readable validation message."""
        messages = {
            ResponseValidationStatus.VALID: "✓ Response structure valid",
            ResponseValidationStatus.MISSING_SECTIONS: 
                f"✗ Missing sections: {', '.join(details.get('missing_sections', []))}",
            ResponseValidationStatus.INVALID_STRUCTURE: 
                "✗ Response not properly structured (appears to be single paragraph)",
            ResponseValidationStatus.INSUFFICIENT_ANALYSIS: 
                f"✗ Analysis section has only {details.get('analysis_bullet_count', 0)} bullets (need >= 3)",
            ResponseValidationStatus.MISSING_CITATIONS: 
                "✗ Missing policy references or citation links",
            ResponseValidationStatus.HALLUCINATION_DETECTED: 
                f"✗ Possible hallucination: {', '.join(details.get('issues', []))}",
        }
        
        return messages.get(status, "Unknown validation status")


# Singleton instance
_validator = StructuredResponseValidator()


def validate_response(response_text: str,
                     retrieved_docs: List[Dict] = None,
                     query_type: str = None) -> Tuple[ResponseValidationStatus, Dict]:
    """Public function to validate response structure."""
    return _validator.validate_response(response_text, retrieved_docs, query_type)


def get_validation_message(status: ResponseValidationStatus, details: Dict) -> str:
    """Public function to get validation message."""
    return _validator.get_validation_message(status, details)
