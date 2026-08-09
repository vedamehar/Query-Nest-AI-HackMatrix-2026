import os
import sqlite3
import json
import logging
import asyncio
import networkx as nx
import matplotlib.pyplot as plt
import io
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path

from pydantic import BaseModel, Field
from config import settings
from services.llm_provider import generate_structured_response
from services.chroma import get_collection_count, get_all_chunks

class Triplet(BaseModel):
    subject: str = Field(..., description="Concise subject of the relationship")
    relation: str = Field(..., description="Active relationship between subject and object")
    object: str = Field(..., description="Concise object of the relationship")

class TripletList(BaseModel):
    triplets: List[Triplet]

logger = logging.getLogger(__name__)

# Data directory for local graph persistence
GRAPH_DB_PATH = os.path.join(os.path.dirname(settings.DB_PATH) if hasattr(settings, 'DB_PATH') else "data", "knowledge_graph.db")
os.makedirs(os.path.dirname(GRAPH_DB_PATH), exist_ok=True)

class GraphService:
    def __init__(self):
        self.db_path = GRAPH_DB_PATH
        self._init_db()

    def _init_db(self):
        """Initialize the local SQLite database for knowledge triplets."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS triplets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT,
                    source_id TEXT,
                    subject TEXT,
                    relation TEXT,
                    object TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_id ON triplets(bot_id)")
            conn.commit()

    async def extract_triplets_from_text(self, text: str, bot_id: str, source_id: str) -> int:
        """
        Use LLM to extract knowledge triplets from text and store them.
        Returns the number of triplets extracted.
        """
        prompt = f"""
        Extract the key entities and their relationships from the following text as a list of triplets.
        Text:
        {text[:2000]} 
        """
        
        try:
            # We use gemini for fast/cheap extraction with a structured schema
            result_dict, _ = await generate_structured_response(
                system_prompt="You are a Knowledge Graph extraction engine. Extract Subject-Relation-Object triplets from the text.",
                user_prompt=prompt,
                provider="gemini",
                model="gemini-2.0-flash",
                user_id="system",
                response_schema=TripletList
            )
            
            extracted_triplets = result_dict.get("triplets", [])
            db_triplets = []
            
            for t in extracted_triplets:
                s, r, o = t.get("subject"), t.get("relation"), t.get("object")
                if s and r and o:
                    db_triplets.append((bot_id, source_id, s, r, o))
            
            if db_triplets:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.executemany(
                        "INSERT INTO triplets (bot_id, source_id, subject, relation, object) VALUES (?, ?, ?, ?, ?)",
                        db_triplets
                    )
                    conn.commit()
                return len(db_triplets)
            
            return 0
        except Exception as e:
            logger.error(f"Error extracting triplets: {e}")
            return 0

    async def get_bot_graph(self, bot_id: str) -> nx.DiGraph:
        """Construct a MultiDiGraph for a specific bot from the local DB."""
        G = nx.DiGraph()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT subject, relation, object FROM triplets WHERE bot_id = ?",
                (bot_id,)
            )
            rows = cursor.fetchall()
            
            for row in rows:
                G.add_edge(row['subject'], row['object'], relation=row['relation'])
        
        return G

    async def visualize_graph_base64(self, bot_id: str) -> Optional[str]:
        """Generate a Matplotlib visualization of the graph and return as base64 string."""
        G = await self.get_bot_graph(bot_id)
        if not G.nodes():
            return None
            
        plt.figure(figsize=(12, 8), facecolor='none')
        # Midnight theme styling
        ax = plt.gca()
        ax.set_facecolor('none')
        
        # Use spring layout for organic look
        pos = nx.spring_layout(G, k=0.5, iterations=50)
        
        # Draw nodes
        nx.draw_networkx_nodes(
            G, pos, 
            node_size=2000, 
            node_color="#8b5cf6", # Brand purple
            alpha=0.8,
            linewidths=2,
            edgecolors="#ffffff"
        )
        
        # Draw edges
        nx.draw_networkx_edges(
            G, pos, 
            width=1.5, 
            alpha=0.4, 
            edge_color="#94a3b8",
            arrowsize=20
        )
        
        # Draw labels
        nx.draw_networkx_labels(
            G, pos, 
            font_size=10, 
            font_color="#1e293b", # Dark slate for contrast on dashboard
            font_weight="bold"
        )
        
        plt.title(f"Knowledge Network: {bot_id}", color="#1e293b", fontsize=16, fontweight='bold', pad=20)
        plt.axis('off')
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=True, dpi=150)
        plt.close()
        buf.seek(0)
        
        return base64.b64encode(buf.read()).decode('utf-8')

    async def get_graph_data(self, bot_id: str) -> Dict[str, Any]:
        """Return graph data in a JSON-friendly format for frontend visualization (e.g. Vis.js)."""
        G = await self.get_bot_graph(bot_id)
        
        nodes = []
        for node in G.nodes():
            nodes.append({"id": node, "label": node})
            
        edges = []
        for u, v, data in G.edges(data=True):
            edges.append({
                "from": u,
                "to": v,
                "label": data.get('relation', '')
            })
            
        return {
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "node_count": G.number_of_nodes(),
                "edge_count": G.number_of_edges()
            }
        }

graph_service = GraphService()
