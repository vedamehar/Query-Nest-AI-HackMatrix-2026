"""
Project Query Routing & Session Management
Detects project-related queries and manages project-specific mode
"""

import re
import logging
from typing import Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# QUERY CLASSIFICATION
# ============================================================================

class QueryType(Enum):
    """Types of queries"""
    COMPLIANCE = "compliance"  # Policy/compliance questions
    PROJECT = "project"        # Project update questions
    GENERAL = "general"        # Other questions


class ProjectQueryRouter:
    """
    Detects project-related queries.
    Routes to project mode when appropriate.
    """
    
    # Keywords that trigger project mode
    PROJECT_KEYWORDS = [
        "project",
        "update",
        "status",
        "progress",
        "milestone",
        "deliverable",
        "timeline",
        "deadline",
        "release",
        "sprint",
        "task",
        "roadmap"
    ]
    
    # Phrases that explicitly request projects
    PROJECT_PHRASES = [
        "show project",
        "list project",
        "available project",
        "project available",
        "project list",
        "what project",
        "which project",
        "give me project",
        "update on project",
        "status of project",
        "progress on project"
    ]
    
    # Phrases that explicitly exit project mode
    EXIT_PHRASES = [
        "exit project",
        "leave project",
        "stop project",
        "end project",
        "back to normal",
        "back to chat",
        "main chat"
    ]
    
    def __init__(self):
        self.project_keywords_regex = self._build_regex(self.PROJECT_KEYWORDS)
        self.project_phrases_regex = self._build_regex(self.PROJECT_PHRASES)
        self.exit_phrases_regex = self._build_regex(self.EXIT_PHRASES)
    
    @staticmethod
    def _build_regex(words: list) -> str:
        """Build regex pattern from words"""
        escaped = [re.escape(w) for w in words]
        return r'\b(' + '|'.join(escaped) + r')\b'
    
    def classify_query(self, query: str) -> QueryType:
        """
        Classify query type.
        
        Returns:
            QueryType.PROJECT if project-related
            QueryType.COMPLIANCE if compliance-related
            QueryType.GENERAL otherwise
        """
        query_lower = query.lower()
        
        # Check if it's explicitly asking to exit
        if re.search(self.exit_phrases_regex, query_lower):
            logger.debug("[ROUTER] Query is exit request")
            return QueryType.GENERAL
        
        # Check for explicit project phrases
        if re.search(self.project_phrases_regex, query_lower):
            logger.info("[ROUTER] Query detected as PROJECT (phrase match)")
            return QueryType.PROJECT
        
        # Check for project keywords
        keyword_matches = len(re.findall(self.project_keywords_regex, query_lower))
        if keyword_matches >= 2:  # At least 2 keywords
            logger.info(f"[ROUTER] Query detected as PROJECT ({keyword_matches} keywords)")
            return QueryType.PROJECT
        
        logger.debug("[ROUTER] Query classified as GENERAL")
        return QueryType.GENERAL
    
    def should_show_projects(self, query: str) -> bool:
        """Check if query is asking to see project list"""
        query_lower = query.lower()
        
        show_patterns = [
            r"show.*project",
            r"list.*project",
            r"available.*project",
            r"what.*project.*available",
            r"which.*project"
        ]
        
        for pattern in show_patterns:
            if re.search(pattern, query_lower):
                logger.info("[ROUTER] Query is asking to show projects")
                return True
        
        return False
    
    def should_exit_project_mode(self, query: str) -> bool:
        """Check if query is requesting to exit project mode"""
        query_lower = query.lower()
        
        if re.search(self.exit_phrases_regex, query_lower):
            logger.info("[ROUTER] Query is exit request")
            return True
        
        return False
    
    def extract_project_name(self, query: str) -> Optional[str]:
        """
        Try to extract project name from query.
        
        Examples:
            "What is the update on Project Alpha?" -> "Project Alpha"
            "Tell me about Client Onboarding 2026" -> "Client Onboarding 2026"
        
        Note: This is a heuristic. Exact matching requires access to project list.
        """
        query_lower = query.lower()
        
        # Pattern: "project XYZ" or "Project XYZ"
        match = re.search(r'project\s+([a-zA-Z0-9\s&-]+?)(?:\?|$|\.)', query, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern: capital words after "on" or "about"
        match = re.search(r'(?:on|about)\s+([A-Z][a-zA-Z0-9\s&-]+)', query)
        if match:
            return match.group(1).strip()
        
        return None


# ============================================================================
# PROJECT SESSION STATE
# ============================================================================

class ProjectSessionState:
    """
    Manages project-specific session state.
    
    Tracks:
    - Is user in project mode?
    - Which project is selected?
    - When did they enter project mode?
    """
    
    def __init__(self):
        self.in_project_mode = False
        self.selected_project: Optional[str] = None
        self.project_entry_time: Optional[str] = None
    
    def enter_project_mode(self, project_name: str) -> None:
        """Enter project mode for a specific project"""
        from datetime import datetime
        
        self.in_project_mode = True
        self.selected_project = project_name
        self.project_entry_time = datetime.utcnow().isoformat()
        
        logger.info(f"[PROJECT_MODE] Entered for project: {project_name}")
    
    def exit_project_mode(self) -> None:
        """Exit project mode"""
        logger.info(f"[PROJECT_MODE] Exited from project: {self.selected_project}")
        
        self.in_project_mode = False
        self.selected_project = None
        self.project_entry_time = None
    
    def to_dict(self) -> dict:
        """Serialize for storage"""
        return {
            "in_project_mode": self.in_project_mode,
            "selected_project": self.selected_project,
            "project_entry_time": self.project_entry_time
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ProjectSessionState':
        """Deserialize from storage"""
        state = ProjectSessionState()
        state.in_project_mode = data.get("in_project_mode", False)
        state.selected_project = data.get("selected_project")
        state.project_entry_time = data.get("project_entry_time")
        return state


# ============================================================================
# PROJECT RETRIEVAL FILTER
# ============================================================================

class ProjectRetrievalFilter:
    """
    Filter vector search results by project.
    
    When in project mode, only return documents from selected project.
    """
    
    @staticmethod
    def filter_by_project(results: list, project_name: str) -> list:
        """
        Filter retrieval results to only include selected project.
        
        Args:
            results: List of (similarity_score, metadata) tuples from vector search
            project_name: Project to filter by
        
        Returns:
            Filtered results
        """
        filtered = [
            (score, meta) for score, meta in results
            if (meta.get("source_type") == "project_update" and
                meta.get("project_name") == project_name)
        ]
        
        logger.info(f"[FILTER] Filtered {len(results)} results -> {len(filtered)} for {project_name}")
        return filtered
    
    @staticmethod
    def exclude_project_data(results: list) -> list:
        """
        Filter OUT project data (normal chat mode).
        
        Args:
            results: List of (similarity_score, metadata) tuples
        
        Returns:
            Results without project_update sources
        """
        filtered = [
            (score, meta) for score, meta in results
            if meta.get("source_type") != "project_update"
        ]
        
        return filtered


# ============================================================================
# RESPONSE FORMATTER FOR PROJECT ANSWERS
# ============================================================================

class ProjectResponseFormatter:
    """
    Format LLM responses for project queries.
    
    Uses different structure than compliance responses.
    """
    
    @staticmethod
    def format_project_answer(
        project_name: str,
        last_updated: str,
        llm_answer: str,
        source_files: list
    ) -> str:
        """
        Format project answer with project-specific structure.
        
        Structure:
        1️⃣ PROJECT NAME
        2️⃣ LAST UPDATED
        3️⃣ ANSWER
        4️⃣ SOURCE FILES
        """
        
        formatted = f"""1️⃣ PROJECT NAME
{project_name}

2️⃣ LAST UPDATED
{last_updated}

3️⃣ UPDATE SUMMARY
{llm_answer}

4️⃣ SOURCE FILES
"""
        
        for source in source_files:
            formatted += f"• {source}\n"
        
        return formatted
    
    @staticmethod
    def format_project_list(projects: list) -> str:
        """Format list of available projects"""
        
        if not projects:
            return "No projects available yet. Projects will appear once they are uploaded to the system."
        
        formatted = "📋 AVAILABLE PROJECTS\n\n"
        for i, project in enumerate(projects, 1):
            formatted += f"{i}. {project}\n"
        
        formatted += "\n💡 Tip: Ask about a specific project to get started! E.g., 'What's the update on {projects[0]}?'"
        return formatted
