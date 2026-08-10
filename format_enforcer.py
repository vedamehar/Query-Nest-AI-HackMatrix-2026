"""
Structured Format Enforcer: Ensures all responses follow mandatory compliance report format.
If LLM output doesn't follow format, regenerates it.
"""
from typing import Dict, Any, List
import re


class StructuredFormatEnforcer:
    """Validates and enforces structured compliance report format."""
    
    REQUIRED_SECTIONS = [
        "COMPLIANCE STATUS",
        "RISK LEVEL",
        "POLICY REFERENCES",
        "REFERENCE LINKS"
    ]
    
    OPTIONAL_SECTIONS = [
        "VIOLATIONS IDENTIFIED",
        "REQUIRED CORRECTIONS",
        "FULLY REWRITTEN COMPLIANT VERSION"
    ]
    
    @staticmethod
    def check_format_compliance(response: str) -> Dict[str, Any]:
        """Check if response follows structured format."""
        issues = []
        sections_found = {}
        
        # Check for required sections
        for section in StructuredFormatEnforcer.REQUIRED_SECTIONS:
            if section in response.upper():
                sections_found[section] = True
            else:
                sections_found[section] = False
                if "no approved reference found" not in response.lower():
                    issues.append(f"Missing: {section}")
        
        # Check formatting rules
        response_upper = response.upper()
        
        # Check if entire response is one paragraph
        lines = [l.strip() for l in response.split('\n') if l.strip()]
        non_header_lines = [l for l in lines if not any(s in l.upper() for s in StructuredFormatEnforcer.REQUIRED_SECTIONS + StructuredFormatEnforcer.OPTIONAL_SECTIONS)]
        
        if len(lines) < 15:  # Too few lines - likely single paragraph format
            issues.append("Response format too compact - must use structured sections")
        
        # Check if violations are using bullets
        if "VIOLATIONS" in response_upper:
            violations_section = response[response.upper().find("VIOLATIONS"):response.upper().find("VIOLATIONS") + 500]
            if "VIOLATIONS" in violations_section and "•" not in violations_section and "-" not in violations_section:
                issues.append("Violations must use bullet points")
        
        # Check if corrections are using bullets
        if "REQUIRED CORRECTIONS" in response_upper:
            corrections_section = response[response.upper().find("REQUIRED CORRECTIONS"):response.upper().find("REQUIRED CORRECTIONS") + 500]
            if "REQUIRED CORRECTIONS" in corrections_section and "•" not in corrections_section and "-" not in corrections_section:
                issues.append("Required corrections must use bullet points")
        
        # Check for inline citations (should not exist in rewritten version)
        has_citations_in_rewrite = False
        if "FULLY REWRITTEN" in response_upper:
            rewrite_start = response.upper().find("FULLY REWRITTEN")
            rewrite_section = response[rewrite_start:response.upper().find("POLICY REFERENCES")] if "POLICY REFERENCES" in response.upper() else response[rewrite_start:]
            if "[" in rewrite_section and "]" in rewrite_section:
                has_citations_in_rewrite = True
                issues.append("Rewritten version must not have inline citations")
        
        is_compliant = len(issues) == 0
        
        return {
            "is_compliant": is_compliant,
            "issues": issues,
            "sections_found": sections_found,
            "section_count": sum(1 for v in sections_found.values() if v)
        }
    
    @staticmethod
    def extract_sections(response: str) -> Dict[str, str]:
        """Extract structured sections from response."""
        sections = {}
        
        section_markers = {
            "COMPLIANCE_STATUS": "COMPLIANCE STATUS",
            "VIOLATIONS": "VIOLATIONS IDENTIFIED",
            "RISK_LEVEL": "RISK LEVEL",
            "CORRECTIONS": "REQUIRED CORRECTIONS",
            "REWRITTEN_VERSION": "FULLY REWRITTEN COMPLIANT VERSION",
            "REFERENCES": "POLICY REFERENCES",
            "LINKS": "REFERENCE LINKS"
        }
        
        for key, marker in section_markers.items():
            pattern = f"{marker}(.*?)(?=(?:{'|'.join([m for m in section_markers.values() if m != marker])}|$))"
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                sections[key] = match.group(1).strip()
        
        return sections
    
    @staticmethod
    def enforce_format(response: str) -> str:
        """Ensure response follows format. If not, add structure markers."""
        
        # Check if already compliant
        check = StructuredFormatEnforcer.check_format_compliance(response)
        
        if check["is_compliant"]:
            return response
        
        # If response is "No approved reference found", return as-is
        if "No approved reference found" in response:
            return response
        
        # Try to parse and restructure
        # For now, add visual separators if missing
        formatted = []
        
        # Add section headers if missing
        if "COMPLIANCE STATUS" not in response and "Approved" in response:
            formatted.append("1️⃣ COMPLIANCE STATUS")
            formatted.append("Approved\n")
        elif "COMPLIANCE STATUS" not in response and "Blocked" in response:
            formatted.append("1️⃣ COMPLIANCE STATUS")
            formatted.append("Blocked\n")
        
        formatted.append(response)
        
        return "\n".join(formatted)
    
    @staticmethod
    def generate_from_components(compliance_status: str, 
                                violations: List[str] = None,
                                risk_level: str = "",
                                corrections: List[str] = None,
                                rewritten: str = "",
                                references: List[str] = None,
                                links: List[tuple] = None) -> str:
        """Generate properly formatted response from components."""
        
        sections = []
        
        # Section 1: Compliance Status
        sections.append("1️⃣ COMPLIANCE STATUS")
        sections.append(compliance_status)
        sections.append("")
        
        # Section 2: Violations
        if violations:
            sections.append("2️⃣ VIOLATIONS IDENTIFIED")
            for violation in violations:
                sections.append(f"• {violation}")
            sections.append("")
        
        # Section 3: Risk Level
        if risk_level:
            sections.append("3️⃣ RISK LEVEL")
            sections.append(risk_level)
            sections.append("")
        
        # Section 4: Corrections
        if corrections:
            sections.append("4️⃣ REQUIRED CORRECTIONS")
            for correction in corrections:
                sections.append(f"• {correction}")
            sections.append("")
        
        # Section 5: Rewritten Version
        if rewritten:
            sections.append("5️⃣ FULLY REWRITTEN COMPLIANT VERSION")
            sections.append(rewritten)
            sections.append("")
        
        # Section 6: References
        if references:
            sections.append("6️⃣ POLICY REFERENCES")
            for ref in references:
                sections.append(f"{ref}")
            sections.append("")
        
        # Section 7: Links
        if links:
            sections.append("7️⃣ REFERENCE LINKS")
            for name, path in links:
                sections.append(f"{name} → {path}")
        
        return "\n".join(sections)
