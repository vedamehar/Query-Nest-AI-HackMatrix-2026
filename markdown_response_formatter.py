"""
Markdown Response Formatter: Ensures compliance responses are formatted as proper Markdown
for client-side rendering.
"""
from typing import Dict, Any, List, Tuple


class MarkdownResponseFormatter:
    """Formats compliance responses as clean, renderable Markdown."""
    
    @staticmethod
    def format_structured_response(
        compliance_status: str,
        violations: List[Dict[str, str]] = None,
        risk_level: str = "",
        corrections: List[str] = None,
        rewritten_version: str = "",
        references: List[str] = None,
        reference_links: List[Tuple[str, str]] = None
    ) -> str:
        """
        Generate a properly formatted Markdown response.
        
        All sections are clearly separated with newlines.
        Markdown renderers will parse this correctly.
        """
        sections = []
        
        # Section 1: Compliance Status
        sections.append("## 1️⃣ COMPLIANCE STATUS\n")
        sections.append(f"{compliance_status}\n")
        
        # Section 2: Violations (if any)
        if violations:
            sections.append("\n## 2️⃣ VIOLATIONS IDENTIFIED\n")
            for violation in violations:
                issue = violation.get("issue", "")
                policy = violation.get("policy", "Unknown Policy")
                section_ref = violation.get("section", "")
                
                sections.append(f"- **{issue}**")
                sections.append(f"  - Policy: {policy}, {section_ref}\n")
        
        # Section 3: Risk Level
        if risk_level:
            sections.append("\n## 3️⃣ RISK LEVEL\n")
            sections.append(f"**{risk_level}**\n")
        
        # Section 4: Required Corrections (if any)
        if corrections:
            sections.append("\n## 4️⃣ REQUIRED CORRECTIONS\n")
            for correction in corrections:
                sections.append(f"- {correction}")
            sections.append("")
        
        # Section 5: Rewritten Version
        if rewritten_version:
            sections.append("\n## 5️⃣ FULLY REWRITTEN COMPLIANT VERSION\n")
            sections.append(f"{rewritten_version}\n")
        
        # Section 6: Policy References
        if references:
            sections.append("\n## 6️⃣ POLICY REFERENCES\n")
            for ref in references:
                sections.append(f"- {ref}")
            sections.append("")
        
        # Section 7: Reference Links
        if reference_links:
            sections.append("\n## 7️⃣ REFERENCE LINKS\n")
            for name, path in reference_links:
                sections.append(f"- **{name}** → `{path}`")
            sections.append("")
        
        # Join with newlines (Markdown parsers need explicit line breaks)
        markdown = "\n".join(sections)
        
        # Clean up excessive newlines
        while "\n\n\n" in markdown:
            markdown = markdown.replace("\n\n\n", "\n\n")
        
        return markdown.strip()
    
    @staticmethod
    def extract_sections_from_text(text: str) -> Dict[str, Any]:
        """Extract structured sections from formatted text."""
        sections = {
            "compliance_status": "",
            "violations": [],
            "risk_level": "",
            "corrections": [],
            "rewritten_version": "",
            "references": [],
            "reference_links": []
        }
        
        lines = text.split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if "COMPLIANCE STATUS" in line.upper():
                current_section = "compliance_status"
                continue
            elif "VIOLATIONS" in line.upper():
                current_section = "violations"
                continue
            elif "RISK LEVEL" in line.upper():
                current_section = "risk_level"
                continue
            elif "REQUIRED CORRECTIONS" in line.upper():
                current_section = "corrections"
                continue
            elif "FULLY REWRITTEN" in line.upper():
                current_section = "rewritten_version"
                continue
            elif "POLICY REFERENCES" in line.upper():
                current_section = "references"
                continue
            elif "REFERENCE LINKS" in line.upper():
                current_section = "reference_links"
                continue
            
            # Extract content based on current section
            if line and not line.startswith("#"):
                if current_section == "compliance_status" and not sections["compliance_status"]:
                    sections["compliance_status"] = line
                elif current_section == "violations" and line.startswith("-"):
                    sections["violations"].append(line.lstrip("- "))
                elif current_section == "risk_level" and not sections["risk_level"]:
                    sections["risk_level"] = line
                elif current_section == "corrections" and line.startswith("-"):
                    sections["corrections"].append(line.lstrip("- "))
                elif current_section == "rewritten_version":
                    sections["rewritten_version"] += line + " "
                elif current_section == "references" and line.startswith("-"):
                    sections["references"].append(line.lstrip("- "))
                elif current_section == "reference_links" and line.startswith("-"):
                    sections["reference_links"].append(line.lstrip("- "))
        
        # Clean up
        sections["rewritten_version"] = sections["rewritten_version"].strip()
        
        return sections
    
    @staticmethod
    def ensure_markdown_format(response: str) -> str:
        """
        Ensure response is properly formatted as Markdown.
        If not, wrap it.
        """
        # If response starts with # (heading), it's already Markdown
        if response.strip().startswith("#"):
            return response
        
        # If response contains section headers, it's already structured
        if any(marker in response for marker in ["## COMPLIANCE", "## 1️⃣", "## 2️⃣"]):
            return response
        
        # Otherwise, wrap in basic Markdown
        # This shouldn't happen with current system prompt, but fallback
        return f"""## Response

{response}"""
    
    @staticmethod
    def validate_markdown_structure(markdown: str) -> Tuple[bool, List[str]]:
        """
        Validate that Markdown has proper structure.
        
        Returns: (is_valid, issues)
        """
        issues = []
        
        # Check for required sections
        required_sections = [
            "COMPLIANCE STATUS",
            "RISK LEVEL"
        ]
        
        for section in required_sections:
            if section not in markdown.upper():
                issues.append(f"Missing: {section}")
        
        # Check for excessive paragraphing (shouldn't all be one paragraph)
        paragraphs = [p for p in markdown.split("\n\n") if p.strip()]
        if len(paragraphs) < 3 and len(markdown) > 100:
            issues.append("Response appears to be single paragraph")
        
        # Check for proper line breaks
        if "\n" not in markdown:
            issues.append("No line breaks in response")
        
        is_valid = len(issues) == 0
        
        return is_valid, issues
