"""
Multi-Version Document Retriever

Retrieval system supporting multiple document versions with:
- Version-aware similarity search
- Conflict detection across versions
- Multi-version citation support
- Active/Inactive version filtering
"""

from typing import Dict, List, Tuple, Optional
import json
from dataclasses import dataclass
from datetime import datetime
import numpy as np

# from faiss_store import FAISSVectorStore
# from document_version_schema import DocumentVersionSchema


@dataclass
class RetrievedChunk:
    """Retrieved chunk with metadata."""
    chunk_id: str
    text: str
    document_name: str
    version: str
    page_number: int
    similarity_score: float
    is_active: bool
    section_title: str


@dataclass
class VersionConflict:
    """Version conflict information."""
    document_name: str
    conflict_type: str  # 'ADDED', 'REMOVED', 'MODIFIED'
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description: str
    old_version: Optional[str]
    new_version: Optional[str]


class MultiVersionRetriever:
    """Retrieve documents with multi-version support."""
    
    def __init__(self, db_schema, faiss_store, embedding_model):
        """
        Initialize multi-version retriever.
        
        Args:
            db_schema: DocumentVersionSchema instance
            faiss_store: FAISS vector store instance
            embedding_model: Embedding model instance
        """
        self.db = db_schema
        self.faiss = faiss_store
        self.embedding_model = embedding_model
        
        # Cache for active document versions
        self._active_versions_cache = {}
        self._cache_timestamp = 0
    
    def retrieve(self,
                query: str,
                top_k: int = 5,
                include_historical: bool = False) -> Dict:
        """
        Retrieve documents with multi-version support.
        
        Returns:
        {
            'chunks': [RetrievedChunk],
            'citations': [{document, version, page}],
            'conflicts': [VersionConflict],
            'metadata': {documents_found, versions_found, has_conflicts}
        }
        """
        
        print(f"[RETRIEVAL] Query: {query[:50]}... | Top-K: {top_k}")
        
        # Step 1: Embed query
        query_embedding = self.embedding_model.encode(query)
        print(f"[RETRIEVAL] Query embedded")
        
        # Step 2: Vector search
        faiss_results = self._vector_search(query_embedding, top_k * 3)
        print(f"[RETRIEVAL] Found {len(faiss_results)} FAISS results")
        
        # Step 3: Fetch metadata and filter active
        active_chunks = self._fetch_and_filter_active(faiss_results)
        print(f"[RETRIEVAL] {len(active_chunks)} active chunks after filtering")
        
        if not active_chunks:
            return self._build_empty_response()
        
        # Step 4: Group by document and version
        chunks_by_doc = self._group_by_document(active_chunks)
        print(f"[RETRIEVAL] Grouped into {len(chunks_by_doc)} documents")
        
        # Step 5: Detect conflicts
        conflicts = self._detect_conflicts(chunks_by_doc)
        if conflicts:
            print(f"[RETRIEVAL] Detected {len(conflicts)} conflicts")
        
        # Step 6: Build response
        response = {
            'chunks': active_chunks[:top_k],
            'citations': self._build_citations(active_chunks[:top_k]),
            'conflicts': conflicts,
            'metadata': {
                'documents_found': len(chunks_by_doc),
                'versions_found': sum(len(versions) for versions in chunks_by_doc.values()),
                'has_conflicts': len(conflicts) > 0,
                'query_embedding_time': 0.05,  # Placeholder
                'retrieval_time': 0.1  # Placeholder
            }
        }
        
        return response
    
    def _vector_search(self, query_embedding: np.ndarray, k: int) -> List[Tuple]:
        """
        Search FAISS index for similar vectors.
        Returns list of (faiss_index, distance) tuples.
        """
        try:
            # Search in FAISS
            distances, indices = self.faiss.search(
                np.array([query_embedding]).astype('float32'),
                k=k
            )
            
            # Return results
            results = []
            for idx, dist in zip(indices[0], distances[0]):
                if idx == -1:  # Invalid result
                    continue
                results.append((idx, dist))
            
            return results
        
        except Exception as e:
            print(f"[RETRIEVAL] FAISS search error: {str(e)}")
            return []
    
    def _fetch_and_filter_active(self, faiss_results: List[Tuple]) -> List[RetrievedChunk]:
        """
        Fetch metadata for FAISS results and filter to ACTIVE versions only.
        """
        chunks = []
        
        for faiss_idx, distance in faiss_results:
            try:
                # Get metadata from database
                metadata = self._get_embedding_metadata(faiss_idx)
                
                if not metadata:
                    continue
                
                # Only include ACTIVE versions
                if not metadata.get('is_active', False):
                    print(f"[RETRIEVAL] Skipping inactive: {metadata.get('chunk_id')}")
                    continue
                
                # Parse metadata JSON
                meta_json = json.loads(metadata.get('metadata_json', '{}'))
                
                chunk = RetrievedChunk(
                    chunk_id=metadata['chunk_id'],
                    text=meta_json.get('text', ''),
                    document_name=metadata['document_name'],
                    version=metadata['version'],
                    page_number=metadata['page_number'],
                    similarity_score=1 - (distance / 100),  # Normalize distance to similarity
                    is_active=metadata['is_active'],
                    section_title=meta_json.get('section_title', '')
                )
                
                chunks.append(chunk)
            
            except Exception as e:
                print(f"[RETRIEVAL] Error processing FAISS result {faiss_idx}: {str(e)}")
                continue
        
        # Sort by similarity
        chunks.sort(key=lambda x: x.similarity_score, reverse=True)
        return chunks
    
    def _get_embedding_metadata(self, faiss_idx: int) -> Optional[Dict]:
        """Get metadata for a FAISS index."""
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT embedding_id, version_id, document_name, version,
                   document_type, page_number, chunk_id, is_active,
                   metadata_json
            FROM embedding_metadata
            WHERE faiss_index = ?
        """, (faiss_idx,))
        
        row = cursor.fetchone()
        if row:
            return {
                'embedding_id': row[0],
                'version_id': row[1],
                'document_name': row[2],
                'version': row[3],
                'document_type': row[4],
                'page_number': row[5],
                'chunk_id': row[6],
                'is_active': row[7],
                'metadata_json': row[8]
            }
        
        return None
    
    def _group_by_document(self, chunks: List[RetrievedChunk]) -> Dict:
        """Group chunks by document name and version."""
        grouped = {}  # {doc_name: {version: [chunks]}}
        
        for chunk in chunks:
            doc_name = chunk.document_name
            version = chunk.version
            
            if doc_name not in grouped:
                grouped[doc_name] = {}
            
            if version not in grouped[doc_name]:
                grouped[doc_name][version] = []
            
            grouped[doc_name][version].append(chunk)
        
        return grouped
    
    def _detect_conflicts(self, chunks_by_doc: Dict) -> List[VersionConflict]:
        """
        Detect conflicts between document versions.
        """
        conflicts = []
        
        for doc_name, versions in chunks_by_doc.items():
            if len(versions) <= 1:
                continue  # No conflict if only one version
            
            # Multiple versions found - check for conflicts
            version_list = sorted(versions.keys())
            
            for i in range(len(version_list) - 1):
                v1 = version_list[i]
                v2 = version_list[i + 1]
                
                # Query conflict table
                cursor = self.db.connection.cursor()
                cursor.execute("""
                    SELECT id, change_type, severity, conflict_description
                    FROM version_conflicts
                    WHERE document_name = ?
                    AND (
                        (old_version_id IN (
                            SELECT id FROM document_versions
                            WHERE document_name = ? AND version = ?
                        ))
                        OR
                        (new_version_id IN (
                            SELECT id FROM document_versions
                            WHERE document_name = ? AND version = ?
                        ))
                    )
                """, (doc_name, doc_name, v1, doc_name, v2))
                
                rows = cursor.fetchall()
                
                for row in rows:
                    conflict = VersionConflict(
                        document_name=doc_name,
                        conflict_type=row[1],
                        severity=row[2],
                        description=row[3] or f"Rule changed between {v1} and {v2}",
                        old_version=v1,
                        new_version=v2
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _build_citations(self, chunks: List[RetrievedChunk]) -> List[Dict]:
        """Build citation references from chunks."""
        citations = []
        seen = set()  # Track unique citations
        
        for chunk in chunks:
            citation_key = (chunk.document_name, chunk.version, chunk.page_number)
            
            if citation_key not in seen:
                citations.append({
                    'document': chunk.document_name,
                    'version': chunk.version,
                    'page': chunk.page_number,
                    'chunk_id': chunk.chunk_id,
                    'is_active': chunk.is_active
                })
                seen.add(citation_key)
        
        return citations
    
    def _build_empty_response(self) -> Dict:
        """Build response when no documents found."""
        return {
            'chunks': [],
            'citations': [],
            'conflicts': [],
            'metadata': {
                'documents_found': 0,
                'versions_found': 0,
                'has_conflicts': False
            }
        }
    
    def retrieve_specific_version(self,
                                 query: str,
                                 document_name: str,
                                 version: str,
                                 top_k: int = 5) -> Dict:
        """
        Retrieve from specific document version.
        Useful for historical lookups.
        """
        print(f"[RETRIEVAL] Specific version: {document_name} {version}")
        
        # Get version ID
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT id FROM document_versions
            WHERE document_name = ? AND version = ?
        """, (document_name, version))
        
        row = cursor.fetchone()
        if not row:
            return self._build_empty_response()
        
        version_id = row[0]
        
        # Get all chunks for this version
        cursor.execute("""
            SELECT embedding_id FROM embedding_metadata
            WHERE version_id = ?
        """, (version_id,))
        
        embedding_ids = [row[0] for row in cursor.fetchall()]
        
        if not embedding_ids:
            return self._build_empty_response()
        
        # Embed query and search (would need to filter FAISS results)
        query_embedding = self.embedding_model.encode(query)
        
        # This is simplified - in production would need to filter FAISS
        faiss_results = self._vector_search(query_embedding, top_k)
        
        # Filter to only chunks from requested version
        version_chunks = self._fetch_and_filter_active(faiss_results)
        version_chunks = [c for c in version_chunks 
                         if c.version == version and c.document_name == document_name]
        
        return {
            'chunks': version_chunks[:top_k],
            'citations': self._build_citations(version_chunks[:top_k]),
            'conflicts': [],
            'metadata': {
                'documents_found': 1,
                'versions_found': 1,
                'has_conflicts': False,
                'requested_version': version
            }
        }
    
    def get_version_history(self, document_name: str) -> List[Dict]:
        """Get version history for a document."""
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT id, version, status, is_active, upload_timestamp, chunk_count
            FROM document_versions
            WHERE document_name = ?
            ORDER BY major_version DESC, minor_version DESC
        """, (document_name,))
        
        versions = []
        for row in cursor.fetchall():
            versions.append({
                'version_id': row[0],
                'version': row[1],
                'status': row[2],
                'is_active': row[3],
                'upload_timestamp': row[4],
                'chunk_count': row[5]
            })
        
        return versions
    
    def compare_versions(self,
                        document_name: str,
                        version1: str,
                        version2: str) -> Dict:
        """Compare two versions of a document."""
        
        print(f"[COMPARE] {document_name}: {version1} vs {version2}")
        
        cursor = self.db.connection.cursor()
        
        # Get version IDs
        cursor.execute("""
            SELECT id FROM document_versions
            WHERE document_name = ? AND version IN (?, ?)
        """, (document_name, version1, version2))
        
        rows = cursor.fetchall()
        if len(rows) != 2:
            return {'error': 'One or both versions not found'}
        
        v1_id, v2_id = rows[0][0], rows[1][0]
        
        # Get conflicts between versions
        cursor.execute("""
            SELECT change_type, severity, conflict_description
            FROM version_conflicts
            WHERE document_name = ?
            AND (
                (old_version_id = ? AND new_version_id = ?)
                OR
                (old_version_id = ? AND new_version_id = ?)
            )
        """, (document_name, v1_id, v2_id, v2_id, v1_id))
        
        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'type': row[0],
                'severity': row[1],
                'description': row[2]
            })
        
        # Get chunk counts
        cursor.execute("""
            SELECT COUNT(*) FROM document_chunks WHERE version_id = ?
        """, (v1_id,))
        v1_chunks = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM document_chunks WHERE version_id = ?
        """, (v2_id,))
        v2_chunks = cursor.fetchone()[0]
        
        return {
            'version1': version1,
            'version2': version2,
            'v1_chunks': v1_chunks,
            'v2_chunks': v2_chunks,
            'changes': conflicts,
            'change_summary': {
                'added': sum(1 for c in conflicts if c['type'] == 'ADDED'),
                'removed': sum(1 for c in conflicts if c['type'] == 'REMOVED'),
                'modified': sum(1 for c in conflicts if c['type'] == 'MODIFIED')
            }
        }


# Singleton instance
_retriever_instance = None


def get_multi_version_retriever() -> MultiVersionRetriever:
    """Get singleton retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        raise RuntimeError("Multi-version retriever not initialized")
    return _retriever_instance


def initialize_retriever(db_schema, faiss_store, embedding_model):
    """Initialize multi-version retriever."""
    global _retriever_instance
    _retriever_instance = MultiVersionRetriever(db_schema, faiss_store, embedding_model)
    return _retriever_instance
