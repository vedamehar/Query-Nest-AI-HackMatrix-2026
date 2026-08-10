"""
Chat Session Management: Conversation grouping with context memory.

Stores multi-turn conversations separately from audit logs.
Each session maintains query-response pairs for context injection.
"""

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import uuid


@dataclass
class Message:
    """Single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    retrieved_docs: List[Dict[str, Any]] = field(default_factory=list)
    compliance_decision: Optional[Dict[str, Any]] = None
    video_id: Optional[str] = None  # Track if message relates to specific video
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict) -> 'Message':
        return Message(**d)


@dataclass
class ChatSession:
    """Conversation session with multiple messages."""
    session_id: str
    user_id: str
    created_at: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    active_video_id: Optional[str] = None  # Track if session is in video mode
    
    def add_message(self, role: str, content: str, 
                   retrieved_docs: List[Dict] = None,
                   compliance_decision: Dict = None,
                   video_id: str = None):
        """Add message to session."""
        msg = Message(
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat(),
            retrieved_docs=retrieved_docs or [],
            compliance_decision=compliance_decision,
            video_id=video_id
        )
        self.messages.append(msg.to_dict())
    
    def get_last_n_messages(self, n: int = 5) -> List[Message]:
        """Get last n query-response pairs (up to 2n messages)."""
        # Convert dicts back to Message objects
        messages = [Message.from_dict(m) for m in self.messages]
        
        # Get last 2n messages (n pairs), but not more than available
        limit = min(len(messages), n * 2)
        return messages[-limit:] if limit > 0 else []
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict) -> 'ChatSession':
        """Reconstruct session from dict."""
        return ChatSession(**d)


class SessionManager:
    """Manages session persistence and retrieval."""
    
    def __init__(self, sessions_dir: str = "data/sessions"):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        print(f"[SESSION] Manager initialized at: {self.sessions_dir}")
    
    def create_session(self, user_id: str = "default_user") -> str:
        """Create new chat session."""
        session_id = str(uuid.uuid4())[:8]
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow().isoformat()
        )
        self.save_session(session)
        print(f"[SESSION] Created: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Load session from disk."""
        session_path = self.sessions_dir / f"{session_id}.json"
        
        if not session_path.exists():
            print(f"[SESSION] Not found: {session_id}")
            return None
        
        try:
            with open(session_path, 'r') as f:
                data = json.load(f)
                session = ChatSession.from_dict(data)
                print(f"[SESSION] Loaded: {session_id} ({len(session.messages)} messages)")
                return session
        except Exception as e:
            print(f"[SESSION] Error loading {session_id}: {e}")
            return None
    
    def save_session(self, session: ChatSession):
        """Save session to disk."""
        session_path = self.sessions_dir / f"{session.session_id}.json"
        
        try:
            with open(session_path, 'w') as f:
                json.dump(session.to_dict(), f, indent=2)
            print(f"[SESSION] Saved: {session.session_id}")
        except Exception as e:
            print(f"[SESSION] Error saving {session.session_id}: {e}")
    
    def list_sessions(self, user_id: str = "default_user") -> List[Dict]:
        """List all sessions for user."""
        sessions = []
        
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                    session = ChatSession.from_dict(data)
                    
                    # Filter by user
                    if session.user_id == user_id:
                        # Get title from first user message
                        title = "Untitled"
                        if session.messages:
                            for msg in session.messages:
                                if msg.get("role") == "user":
                                    title = msg.get("content", "Untitled")[:50]  # First 50 chars
                                    break
                        
                        sessions.append({
                            "id": session.session_id,
                            "session_id": session.session_id,
                            "title": title,
                            "created_at": session.created_at,
                            "message_count": len(session.messages),
                            "active_video_id": session.active_video_id
                        })
            except Exception as e:
                print(f"[SESSION] Error reading {session_file}: {e}")
        
        # Sort by creation date (newest first)
        sessions.sort(key=lambda x: x['created_at'], reverse=True)
        return sessions
    
    def add_message_to_session(self, session_id: str, role: str, content: str,
                              retrieved_docs: List[Dict] = None,
                              compliance_decision: Dict = None,
                              video_id: str = None):
        """Add message to existing session."""
        session = self.get_session(session_id)
        
        if not session:
            print(f"[SESSION] Cannot add message: session {session_id} not found")
            return False
        
        session.add_message(
            role=role,
            content=content,
            retrieved_docs=retrieved_docs,
            compliance_decision=compliance_decision,
            video_id=video_id
        )
        self.save_session(session)
        return True
    
    def set_active_video(self, session_id: str, video_id: Optional[str]):
        """Set active video for session."""
        session = self.get_session(session_id)
        
        if not session:
            return False
        
        session.active_video_id = video_id
        self.save_session(session)
        
        if video_id:
            print(f"[SESSION] {session_id} → video mode: {video_id}")
        else:
            print(f"[SESSION] {session_id} → normal mode")
        
        return True
    
    def get_context_string(self, session_id: str, max_messages: int = 5) -> str:
        """Get formatted context from last N messages in THIS session ONLY.
        
        Args:
            session_id: The CURRENT session ID (never from other sessions)
            max_messages: Max messages to include (default 5 for isolation)
        
        Returns:
            Context string with conversation history
        """
        session = self.get_session(session_id)
        
        if not session or len(session.messages) == 0:
            return ""
        
        # Log: verify this is the right session and session isolation
        print(f"[SESSION] Building context for session {session_id}: "
              f"{len(session.messages)} total messages in this session")
        
        # Get last messages from THIS session only
        messages = session.get_last_n_messages(n=max_messages // 2)
        
        if not messages:
            return ""
        
        # Build context string
        context_lines = ["## Conversation Context"]
        
        for msg in messages:
            role = "You" if msg.role == "assistant" else "User"
            # Truncate long responses to prevent context bloat
            content = msg.content[:300] if len(msg.content) > 300 else msg.content
            context_lines.append(f"\n**{role}:** {content}")
        
        result = "\n".join(context_lines)
        print(f"[SESSION] Context built from {len(messages)} messages, "
              f"size: {len(result)} chars (session {session_id})")
        return result


# Global singleton
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get or create global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
