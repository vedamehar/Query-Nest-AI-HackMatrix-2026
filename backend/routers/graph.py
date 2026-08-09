from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Dict, Any
import logging

from services.graph_service import graph_service
from services.chroma import get_all_chunks
from database import get_tenant_by_bot_id

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])
logger = logging.getLogger(__name__)

@router.get("/{bot_id}")
async def get_graph(bot_id: str):
    """Retrieve the interactive graph data for a specific bot."""
    try:
        data = await graph_service.get_graph_data(bot_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{bot_id}/visualize")
async def visualize_graph(bot_id: str):
    """Generate and return a base64 encoded image of the knowledge graph."""
    try:
        img_b64 = await graph_service.visualize_graph_base64(bot_id)
        if not img_b64:
            return {"status": "empty", "message": "No graph data available for this bot yet."}
        return {"status": "success", "image": img_b64}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{bot_id}/rebuild")
async def rebuild_graph(bot_id: str, background_tasks: BackgroundTasks):
    """
    Trigger a full rebuild of the knowledge graph from all ingested document chunks.
    This runs as a background task.
    """
    try:
        # Verify bot exists
        tenant = await get_tenant_by_bot_id(bot_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Define the background task
        async def process_content():
            try:
                logger.info(f"Starting graph rebuild for bot: {bot_id}")
                # Fetch all chunks (this assumes we have a way to get chunks for a bot)
                # In SiteSense, Chroma is used. 
                chunks = await get_all_chunks(bot_id)
                
                # To avoid over-using LLM, we might want to sample or group chunks
                # For now, let's process the first N unique segments to build a representative graph
                processed_count = 0
                max_chunks = 50 # Limit for safety
                
                # Group chunks by source for better context
                source_groups = {}
                for c in chunks[:max_chunks]:
                    sid = c.get('metadata', {}).get('source_id', 'unknown')
                    if sid not in source_groups:
                        source_groups[sid] = []
                    source_groups[sid].append(c.get('document', ''))
                
                for sid, text_list in source_groups.items():
                    combined_text = "\n".join(text_list)
                    count = await graph_service.extract_triplets_from_text(combined_text, bot_id, sid)
                    processed_count += count
                
                logger.info(f"Graph rebuild complete for {bot_id}. Extracted {processed_count} triplets.")
            except Exception as e:
                logger.error(f"Error in background graph task: {e}")

        background_tasks.add_task(process_content)
        return {"status": "accepted", "message": "Graph rebuild started in background."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
