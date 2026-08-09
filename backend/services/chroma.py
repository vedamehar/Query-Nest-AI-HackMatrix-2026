"""
SiteSense AI — Vector DB Service (Pinecone Edition)

This version replaces ChromaDB with Pinecone Serverless to support
Render deployments without needing persistent local storage disks.
Note: The file is kept as 'chroma.py' to prevent breaking imports across the app.
"""

from __future__ import annotations
import logging
from pinecone import Pinecone
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level client — lazy-initialised
# ---------------------------------------------------------------------------
_pc_client: Pinecone | None = None
_index = None

def get_pinecone_index():
    """
    Return a reusable Pinecone index client.
    """
    global _pc_client, _index
    if _pc_client is None:
        if not settings.PINECONE_API_KEY:
            logger.error("PINECONE_API_KEY is missing! Vector operations will fail.")
            
        _pc_client = Pinecone(api_key=settings.PINECONE_API_KEY)
        _index = _pc_client.Index(settings.PINECONE_INDEX_NAME)
    return _index


# ===================================================================
#  HELPERS
# ===================================================================

def get_namespace(bot_id: str) -> str:
    """Pinecone uses namespaces instead of collections for tenant isolation."""
    return f"tenant_{bot_id.replace('-', '_')}"


# ===================================================================
#  COLLECTION / NAMESPACE LIFECYCLE
# ===================================================================

async def get_or_create_collection(bot_id: str):
    """
    Compatibility wrapper. Pinecone creates namespaces implicitly 
    on the first upsert, so we just return the index and namespace string.
    """
    index = get_pinecone_index()
    return index


async def collection_exists(bot_id: str) -> bool:
    """Check if the namespace has any vectors."""
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        ns = get_namespace(bot_id)
        return ns in stats.get("namespaces", {})
    except Exception:
        return False


async def get_collection_count(bot_id: str) -> int:
    """Return the vector count for a specific tenant namespace."""
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        ns = get_namespace(bot_id)
        if ns in stats.get("namespaces", {}):
            return stats["namespaces"][ns]["vector_count"]
        return 0
    except Exception:
        return 0


async def delete_tenant_collection(bot_id: str) -> bool:
    """Delete all vectors in the tenant's namespace."""
    try:
        index = get_pinecone_index()
        ns = get_namespace(bot_id)
        index.delete(delete_all=True, namespace=ns)
        return True
    except Exception:
        return False


# ===================================================================
#  CHUNK OPERATIONS
# ===================================================================

async def add_chunks_to_collection(
    bot_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
    ids: list[str],
) -> int:
    """Upsert vectors into Pinecone."""
    if not chunks:
        return 0

    index = get_pinecone_index()
    ns = get_namespace(bot_id)
    
    # Pinecone requires vectors in the format: {"id": "...", "values": [...], "metadata": {...}}
    batch_size = 100  # Pinecone optimal batch size is usually smaller than Chroma
    added = 0

    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        
        vectors_to_upsert = []
        for i in range(start, min(end, len(chunks))):
            meta = metadatas[i].copy() if metadatas[i] else {}
            meta["document"] = chunks[i]  # Pinecone doesn't have a separate document field
            
            vectors_to_upsert.append({
                "id": ids[i],
                "values": embeddings[i],
                "metadata": meta
            })
            
        index.upsert(vectors=vectors_to_upsert, namespace=ns)
        added += len(vectors_to_upsert)

    return added


async def query_collection(
    bot_id: str,
    query_embedding: list[float],
    n_results: int = 10,
) -> dict:
    """Query Pinecone and format results to match the legacy ChromaDB output."""
    empty_result: dict = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }

    try:
        index = get_pinecone_index()
        ns = get_namespace(bot_id)

        # First verify the namespace exists and has vectors
        stats = index.describe_index_stats()
        if ns not in stats.get("namespaces", {}):
            return empty_result
            
        count = stats["namespaces"][ns]["vector_count"]
        if count == 0:
            return empty_result

        n_results = min(n_results, count)

        response = index.query(
            vector=query_embedding,
            top_k=n_results,
            include_metadata=True,
            namespace=ns
        )

        documents = []
        metas = []
        distances = []

        for match in response.get("matches", []):
            metadata = match.get("metadata", {})
            doc = metadata.pop("document", "")  # Extract the text
            
            documents.append(doc)
            metas.append(metadata)
            distances.append(match.get("score", 0.0)) # Pinecone returns similarity score (higher is better)

        return {
            "documents": [documents],
            "metadatas": [metas],
            "distances": [distances],
        }

    except Exception as e:
        logger.error(f"Pinecone query error: {e}")
        return empty_result


async def delete_source_chunks(
    bot_id: str,
    source_id: str,
) -> bool:
    """Delete chunks associated with a specific source_id."""
    try:
        index = get_pinecone_index()
        ns = get_namespace(bot_id)
        
        # Pinecone allows deletion by metadata filter
        index.delete(
            filter={"source_id": {"$eq": source_id}},
            namespace=ns
        )
        return True
    except Exception as e:
        logger.error(f"Pinecone delete_source_chunks error: {e}")
        return False


async def get_all_chunks(bot_id: str) -> list[dict]:
    """
    Retrieve all chunks for a specific bot from Pinecone.
    Because Pinecone doesn't have a direct 'get all' without IDs, 
    we query with a dummy zero-vector and a large top_k for 1024 dimensions.
    """
    try:
        index = get_pinecone_index()
        ns = get_namespace(bot_id)
        
        stats = index.describe_index_stats()
        if ns not in stats.get("namespaces", {}):
            return []
            
        vector_count = stats["namespaces"][ns]["vector_count"]
        if vector_count == 0:
            return []
            
        # Voyage-02 is 1024 dimensions. Create a dummy zero vector.
        dummy_vector = [0.0] * 1024
        
        response = index.query(
            vector=dummy_vector,
            top_k=min(vector_count, 10000), # Cap at 10000 limit
            include_metadata=True,
            namespace=ns
        )
        
        chunks = []
        for match in response.get("matches", []):
            metadata = match.get("metadata", {})
            doc = metadata.pop("document", "")
            chunks.append({
                "document": doc,
                "metadata": metadata
            })
            
        return chunks
    except Exception as e:
        logger.error(f"Error fetching all chunks for {bot_id}: {e}")
        return []
