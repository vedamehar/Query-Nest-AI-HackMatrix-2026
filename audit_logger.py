"""
Audit Logging: Immutable traceability for all queries.
7-year retention, records decision path and model version.
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


class AuditLogger:
    """SQLite-based immutable audit log."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()
    
    def _initialize_db(self):
        """Create audit log schema with migration support."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                query TEXT NOT NULL,
                compliance_decision TEXT NOT NULL,
                compliance_allowed BOOLEAN NOT NULL,
                restricted_entities TEXT,
                retrieved_documents TEXT,
                retrieved_count INTEGER,
                llm_response TEXT,
                response_valid BOOLEAN,
                validation_issues TEXT,
                model_version TEXT,
                ip_address TEXT,
                session_id TEXT,
                context_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ✅ NEW: Migration - Add missing columns to existing table
        # Get list of existing columns
        cursor.execute("PRAGMA table_info(audit_log)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Add session_id column if missing
        if 'session_id' not in existing_columns:
            print("[AUDIT] Migrating database: Adding session_id column...")
            try:
                cursor.execute("ALTER TABLE audit_log ADD COLUMN session_id TEXT")
                print("[AUDIT] ✓ Added session_id column")
            except Exception as e:
                print(f"[AUDIT] ⚠️ Could not add session_id: {e}")
        
        # Add context_used column if missing
        if 'context_used' not in existing_columns:
            print("[AUDIT] Migrating database: Adding context_used column...")
            try:
                cursor.execute("ALTER TABLE audit_log ADD COLUMN context_used BOOLEAN DEFAULT FALSE")
                print("[AUDIT] ✓ Added context_used column")
            except Exception as e:
                print(f"[AUDIT] ⚠️ Could not add context_used: {e}")
        
        # Create indexes
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON audit_log(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON audit_log(session_id)
            """)
            print("[AUDIT] ✓ Indexes created/verified")
        except Exception as e:
            print(f"[AUDIT] ⚠️ Index creation failed (non-critical): {e}")
        
        conn.commit()
        conn.close()
        print("[AUDIT] ✓ Database initialization complete")
    
    def log(self,
            query: str,
            compliance_decision: Dict[str, Any],
            retrieved_documents: List[Dict[str, Any]],
            llm_response: Optional[str] = None,
            response_valid: Optional[bool] = None,
            validation_issues: Optional[List[str]] = None,
            user_id: str = "system",
            model_version: str = "mistral:latest",
            ip_address: str = "127.0.0.1",
            session_id: Optional[str] = None,
            context_used: bool = False) -> int:
        """Log a query and its processing path."""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO audit_log (
                timestamp, user_id, query,
                compliance_decision, compliance_allowed,
                restricted_entities, retrieved_documents, retrieved_count,
                llm_response, response_valid, validation_issues,
                model_version, ip_address, session_id, context_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            user_id,
            query,
            json.dumps(compliance_decision),
            compliance_decision.get("allowed", False),
            json.dumps(compliance_decision.get("restricted_entities", [])),
            json.dumps([doc.get("chunk_id") for doc in retrieved_documents]),
            len(retrieved_documents),
            llm_response,
            response_valid,
            json.dumps(validation_issues or []),
            model_version,
            ip_address,
            session_id,
            context_used
        ))
        
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        
        return log_id
    
    def retrieve_logs(self, 
                     user_id: Optional[str] = None,
                     days: int = 7,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve audit logs for review."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        if user_id:
            cursor.execute("""
                SELECT * FROM audit_log
                WHERE timestamp >= ? AND user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (cutoff_date.isoformat(), user_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM audit_log
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (cutoff_date.isoformat(), limit))
        
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        for log in logs:
            try:
                log["compliance_decision"] = json.loads(log["compliance_decision"])
                log["retrieved_documents"] = json.loads(log["retrieved_documents"])
                log["validation_issues"] = json.loads(log["validation_issues"])
                log["restricted_entities"] = json.loads(log["restricted_entities"])
            except:
                pass
        
        return logs
    
    def purge_old_logs(self, retention_days: int = 365 * 7):
        """Remove logs older than retention period."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        cursor.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff_date.isoformat(),))
        conn.commit()
        conn.close()
    
    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get audit statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        cursor.execute("""
            SELECT
                COUNT(*) as total_queries,
                SUM(CASE WHEN compliance_allowed = 1 THEN 1 ELSE 0 END) as allowed,
                SUM(CASE WHEN compliance_allowed = 0 THEN 1 ELSE 0 END) as blocked,
                SUM(CASE WHEN response_valid = 1 THEN 1 ELSE 0 END) as valid_responses
            FROM audit_log
            WHERE timestamp >= ?
        """, (cutoff_date.isoformat(),))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            "period_days": days,
            "total_queries": row[0] or 0,
            "allowed_queries": row[1] or 0,
            "blocked_queries": row[2] or 0,
            "valid_responses": row[3] or 0
        }
