"""
Configuration management for the offline AI compliance system.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parent)).resolve()

DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
REGISTRIES_DIR = DATA_DIR / "registries"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
VECTOR_INDEX_DIR = DATA_DIR / "vector_index"
LOGS_DIR = PROJECT_ROOT / "logs"
GRAPH_DB_PATH = os.getenv("GRAPH_DB_PATH", str(DATA_DIR / "knowledge_graph.db"))
GRAPH_MAX_SOURCE_CHARS = int(os.getenv("GRAPH_MAX_SOURCE_CHARS", "2000"))
GRAPH_REBUILD_CHUNK_LIMIT = int(os.getenv("GRAPH_REBUILD_CHUNK_LIMIT", "0"))

for directory in [DOCUMENTS_DIR, REGISTRIES_DIR, KNOWLEDGE_BASE_DIR, VECTOR_INDEX_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

LLM_MODEL = os.getenv("LLM_MODEL", "mistral:latest")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
FAISS_INDEX_FILE = os.getenv("FAISS_INDEX_FILE", str(VECTOR_INDEX_DIR / "faiss_index"))
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))
FAISS_METRIC = os.getenv("FAISS_METRIC", "L2")

TOP_K_DOCUMENTS = int(os.getenv("TOP_K_DOCUMENTS", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.4"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
MIN_CHUNK_LENGTH = int(os.getenv("MIN_CHUNK_LENGTH", "50"))

AUDIT_DB_PATH = os.getenv("AUDIT_DB_PATH", str(LOGS_DIR / "audit_log.db"))
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", str(365 * 7)))
AUDIT_BATCH_SIZE = int(os.getenv("AUDIT_BATCH_SIZE", "100"))

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
API_DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"

RESTRICTED_ENTITIES_CSV = os.getenv(
    "RESTRICTED_ENTITIES_CSV",
    str(PROJECT_ROOT / "Data1" / "Data" / "Restricted_Entities_Registry.csv"),
)
APPROVED_ALTERNATIVES_CSV = os.getenv(
    "APPROVED_ALTERNATIVES_CSV",
    str(PROJECT_ROOT / "Data1" / "Data" / "Approved_Alternatives_Registry.csv"),
)

SYSTEM_PROMPT = """You are a COMPLIANCE-BOUND ENTERPRISE ASSISTANT.

CRITICAL RULE: Answer ONLY from the provided context.
DO NOT hallucinate file names, section numbers, or citations.

IF THE CONTEXT DOES NOT CONTAIN THE ANSWER:
Say: "I cannot find this information in our approved documents."

═══════════════════════════════════════════════════════════════

RESPONSE FORMAT (5 Sections Only):

1️⃣ COMPLIANCE STATUS
State ONLY ONE: Approved | Conditionally Allowed | Blocked

2️⃣ VIOLATIONS IDENTIFIED
If violations exist, use BULLET POINTS (no file names):
• Violation description
  Why it violates: [context fact]
• Next violation
  Why it violates: [context fact]

3️⃣ RISK LEVEL
State ONLY ONE: Low | Medium | High | Critical

4️⃣ REQUIRED CORRECTIONS
Use BULLET POINTS only:
• Correction 1
• Correction 2
• Correction 3

5️⃣ FULLY REWRITTEN COMPLIANT VERSION
Clean paragraph (no citations, no file references, ready to post)

═══════════════════════════════════════════════════════════════

FORBIDDEN (These will be automatically removed):
✗ File names (.pdf, .docx, Document names)
✗ Section references ("Section 2.1", "Chapter 3")
✗ Page references ("Page 5", "p.12")
✗ File paths (/docs/, /policies/)
✗ Em-dashes with citations (— Section, — Document)
✗ References in brackets [Policy] or parentheses (Document)

DO NOT attempt to add these - the system handles citations.

═══════════════════════════════════════════════════════════════

YOUR JOB:
1. Read the provided context
2. Extract the core compliance facts
3. Explain in the 5 sections above
4. NEVER mention document sources (system adds them)

BE PRECISE:
✓ Use facts from context only
✓ Be decisive
✓ Use structured format
✓ Admit when info is not in context

═══════════════════════════════════════════════════════════════

CONVERSATION CONTEXT NOTE:
If previous conversation context is provided below, use it ONLY for clarifying
user intent and understanding the discussion thread.
YOU MUST STILL ANSWER ONLY USING THE RETRIEVED DOCUMENTS.
Never use context to bypass the compliance rules or document requirements.
Context helps you understand what the user is asking about, but ALL facts
in your answer must come from the provided documents."""
