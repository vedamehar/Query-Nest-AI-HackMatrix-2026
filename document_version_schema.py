"""
Document Version Control Database Schema

SQLite tables for managing document versions, chunks, embeddings, and conflicts.
Created for production-grade document versioning system.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import json


class DocumentVersionSchema:
    """Database schema for document versioning system."""
    
    def __init__(self, db_path: str = "document_versions.db"):
        """Initialize database connection and create tables."""
        self.db_path = db_path
        self.connection = None
        self.initialize()
    
    def initialize(self):
        """Create database and all tables."""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        
        cursor = self.connection.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create all tables
        self._create_document_versions_table(cursor)
        self._create_document_chunks_table(cursor)
        self._create_embedding_metadata_table(cursor)
        self._create_version_conflicts_table(cursor)
        self._create_ingestion_tasks_table(cursor)
        self._create_ingestion_failures_table(cursor)
        self._create_admin_audit_log_table(cursor)
        
        self.connection.commit()
        print(f"[DB] Database initialized: {self.db_path}")
    
    def _create_document_versions_table(self, cursor):
        """Table for managing document versions."""
        sql = """
        CREATE TABLE IF NOT EXISTS document_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_name TEXT NOT NULL,
            document_type TEXT NOT NULL,
            version TEXT NOT NULL,
            major_version INTEGER NOT NULL,
            minor_version INTEGER NOT NULL,
            status TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT NOT NULL,
            description TEXT,
            page_count INTEGER,
            total_tokens INTEGER,
            chunk_count INTEGER,
            previous_version_id INTEGER,
            content_hash TEXT NOT NULL,
            deleted_at DATETIME,
            deletion_reason TEXT,
            UNIQUE(document_name, version),
            UNIQUE(content_hash),
            FOREIGN KEY (previous_version_id) REFERENCES document_versions(id),
            CHECK(document_type IN ('SOP', 'Policy', 'Internal', 'Technical')),
            CHECK(status IN ('PROCESSING', 'ACTIVE', 'INACTIVE', 'FAILED', 'DEPRECATED')),
            CHECK(file_type IN ('pdf', 'docx', 'md', 'txt'))
        )
        """
        cursor.execute(sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_active ON document_versions(document_name, is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_type ON document_versions(document_type, is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_version_status ON document_versions(status)")
    
    def _create_document_chunks_table(self, cursor):
        """Table for document chunks with metadata."""
        sql = """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            chunk_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            text_length INTEGER,
            token_count INTEGER,
            page_number INTEGER NOT NULL,
            page_start_char INTEGER,
            page_end_char INTEGER,
            section_title TEXT,
            section_hierarchy TEXT,
            embedding_id TEXT,
            embedding_version TEXT,
            is_indexed BOOLEAN DEFAULT 0,
            indexed_at DATETIME,
            UNIQUE(version_id, chunk_id),
            FOREIGN KEY (version_id) REFERENCES document_versions(id)
        )
        """
        cursor.execute(sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_version ON document_chunks(version_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_page ON document_chunks(version_id, page_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON document_chunks(embedding_id)")
    
    def _create_embedding_metadata_table(self, cursor):
        """Table for embedding metadata with FAISS index reference."""
        sql = """
        CREATE TABLE IF NOT EXISTS embedding_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            embedding_id TEXT NOT NULL,
            version_id INTEGER NOT NULL,
            document_name TEXT NOT NULL,
            version TEXT NOT NULL,
            document_type TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            chunk_id TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            faiss_index INTEGER,
            metadata_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            indexed_at DATETIME,
            UNIQUE(embedding_id),
            FOREIGN KEY (version_id) REFERENCES document_versions(id)
        )
        """
        cursor.execute(sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_active ON embedding_metadata(is_active, document_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_version ON embedding_metadata(document_name, version)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_faiss ON embedding_metadata(faiss_index)")
    
    def _create_version_conflicts_table(self, cursor):
        """Table for tracking version conflicts and changes."""
        sql = """
        CREATE TABLE IF NOT EXISTS version_conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_name TEXT NOT NULL,
            old_version_id INTEGER NOT NULL,
            new_version_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            old_chunk_id TEXT,
            new_chunk_id TEXT,
            old_content TEXT,
            new_content TEXT,
            is_conflicting BOOLEAN DEFAULT 0,
            conflict_description TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            severity TEXT,
            FOREIGN KEY (old_version_id) REFERENCES document_versions(id),
            FOREIGN KEY (new_version_id) REFERENCES document_versions(id),
            CHECK(change_type IN ('ADDED', 'REMOVED', 'MODIFIED')),
            CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
        )
        """
        cursor.execute(sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflict_document ON version_conflicts(document_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflict_severity ON version_conflicts(severity)")
    
    def _create_ingestion_tasks_table(self, cursor):
        """Table for tracking ingestion task progress."""
        sql = """
        CREATE TABLE IF NOT EXISTS ingestion_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id TEXT NOT NULL,
            version_id INTEGER NOT NULL,
            current_stage TEXT,
            progress_percentage INTEGER DEFAULT 0,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            status TEXT,
            error_message TEXT,
            chunks_processed INTEGER DEFAULT 0,
            embeddings_generated INTEGER DEFAULT 0,
            processing_time_seconds FLOAT,
            UNIQUE(upload_id),
            FOREIGN KEY (version_id) REFERENCES document_versions(id),
            CHECK(status IN ('QUEUED', 'PROCESSING', 'COMPLETED', 'ERROR'))
        )
        """
        cursor.execute(sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON ingestion_tasks(status)")
    
    def _create_ingestion_failures_table(self, cursor):
        """Table for logging ingestion failures."""
        sql = """
        CREATE TABLE IF NOT EXISTS ingestion_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id TEXT NOT NULL,
            version_id INTEGER NOT NULL,
            stage_failed TEXT,
            error_type TEXT NOT NULL,
            error_message TEXT NOT NULL,
            traceback TEXT,
            failure_stage TEXT,
            recovery_attempted BOOLEAN DEFAULT 0,
            recovery_successful BOOLEAN DEFAULT 0,
            recovery_notes TEXT,
            failure_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (version_id) REFERENCES document_versions(id)
        )
        """
        cursor.execute(sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_failure_upload ON ingestion_failures(upload_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_failure_version ON ingestion_failures(version_id)")
    
    def _create_admin_audit_log_table(self, cursor):
        """Table for admin action audit trail."""
        sql = """
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_username TEXT NOT NULL,
            action TEXT NOT NULL,
            document_name TEXT,
            document_version TEXT,
            version_id INTEGER,
            action_details TEXT,
            success BOOLEAN DEFAULT 1,
            error_message TEXT,
            action_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (version_id) REFERENCES document_versions(id)
        )
        """
        cursor.execute(sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_admin ON admin_audit_log(admin_username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_document ON admin_audit_log(document_name)")
    
    def add_document_version(self, **kwargs) -> int:
        """Add a new document version."""
        cursor = self.connection.cursor()
        
        sql = """
            INSERT INTO document_versions
            (document_name, document_type, version, major_version, minor_version,
             status, file_path, file_size, file_type, uploaded_by, description,
             content_hash, previous_version_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(sql, (
            kwargs.get('document_name'),
            kwargs.get('document_type'),
            kwargs.get('version'),
            kwargs.get('major_version'),
            kwargs.get('minor_version'),
            kwargs.get('status', 'PROCESSING'),
            kwargs.get('file_path'),
            kwargs.get('file_size'),
            kwargs.get('file_type'),
            kwargs.get('uploaded_by'),
            kwargs.get('description'),
            kwargs.get('content_hash'),
            kwargs.get('previous_version_id')
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def add_chunk(self, **kwargs) -> int:
        """Add a document chunk."""
        cursor = self.connection.cursor()
        
        sql = """
            INSERT INTO document_chunks
            (version_id, chunk_id, chunk_index, text_content, text_length,
             token_count, page_number, section_title, section_hierarchy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(sql, (
            kwargs.get('version_id'),
            kwargs.get('chunk_id'),
            kwargs.get('chunk_index'),
            kwargs.get('text_content'),
            kwargs.get('text_length'),
            kwargs.get('token_count'),
            kwargs.get('page_number'),
            kwargs.get('section_title'),
            kwargs.get('section_hierarchy')
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def add_embedding_metadata(self, **kwargs) -> int:
        """Add embedding metadata."""
        cursor = self.connection.cursor()
        
        sql = """
            INSERT INTO embedding_metadata
            (embedding_id, version_id, document_name, version, document_type,
             page_number, chunk_id, is_active, faiss_index, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(sql, (
            kwargs.get('embedding_id'),
            kwargs.get('version_id'),
            kwargs.get('document_name'),
            kwargs.get('version'),
            kwargs.get('document_type'),
            kwargs.get('page_number'),
            kwargs.get('chunk_id'),
            kwargs.get('is_active', 1),
            kwargs.get('faiss_index'),
            kwargs.get('metadata_json')
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def mark_version_inactive(self, version_id: int):
        """Mark a version as inactive."""
        cursor = self.connection.cursor()
        cursor.execute("""
            UPDATE document_versions
            SET is_active = 0, status = 'INACTIVE'
            WHERE id = ?
        """, (version_id,))
        
        cursor.execute("""
            UPDATE embedding_metadata
            SET is_active = 0
            WHERE version_id = ?
        """, (version_id,))
        
        self.connection.commit()
    
    def get_active_documents(self) -> list:
        """Get all active document versions."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT DISTINCT document_name, version, id
            FROM document_versions
            WHERE is_active = 1 AND status = 'ACTIVE'
            ORDER BY document_name, version DESC
        """)
        return cursor.fetchall()
    
    def get_document_versions(self, document_name: str) -> list:
        """Get all versions of a document."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT id, version, status, is_active, upload_timestamp
            FROM document_versions
            WHERE document_name = ?
            ORDER BY major_version DESC, minor_version DESC
        """, (document_name,))
        return cursor.fetchall()
    
    def get_chunks_by_version(self, version_id: int) -> list:
        """Get all chunks for a version."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT id, chunk_id, chunk_index, token_count, page_number,
                   section_title, embedding_id, is_indexed
            FROM document_chunks
            WHERE version_id = ?
            ORDER BY chunk_index
        """, (version_id,))
        return cursor.fetchall()
    
    def get_version_conflicts(self, document_name: str) -> list:
        """Get conflicts for a document."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT id, change_type, is_conflicting, severity, conflict_description
            FROM version_conflicts
            WHERE document_name = ?
            ORDER BY detected_at DESC
        """, (document_name,))
        return cursor.fetchall()
    
    def log_admin_action(self, **kwargs):
        """Log admin action to audit trail."""
        cursor = self.connection.cursor()
        
        sql = """
            INSERT INTO admin_audit_log
            (admin_username, action, document_name, document_version, version_id,
             action_details, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(sql, (
            kwargs.get('admin_username'),
            kwargs.get('action'),
            kwargs.get('document_name'),
            kwargs.get('document_version'),
            kwargs.get('version_id'),
            kwargs.get('action_details'),
            kwargs.get('success', 1),
            kwargs.get('error_message')
        ))
        
        self.connection.commit()
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            print("[DB] Database connection closed")


# Initialize schema on import
if __name__ == "__main__":
    schema = DocumentVersionSchema("document_versions.db")
    print("✓ Database schema initialized")
    
    # Test data
    version_id = schema.add_document_version(
        document_name="Test_Policy",
        document_type="Policy",
        version="v1.0",
        major_version=1,
        minor_version=0,
        file_path="/tmp/test.pdf",
        file_size=1024,
        file_type="pdf",
        uploaded_by="admin",
        content_hash="abc123"
    )
    
    print(f"✓ Test version added: ID {version_id}")
    
    chunk_id = schema.add_chunk(
        version_id=version_id,
        chunk_id="test_v1.0_chunk_001",
        chunk_index=0,
        text_content="Test content",
        text_length=12,
        token_count=5,
        page_number=1,
        section_title="Introduction"
    )
    
    print(f"✓ Test chunk added: ID {chunk_id}")
    
    schema.close()
