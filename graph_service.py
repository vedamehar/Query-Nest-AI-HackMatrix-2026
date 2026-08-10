"""
Knowledge graph service for extracting and serving entity relationships.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import networkx as nx
from pydantic import BaseModel, Field

import config


class Triplet(BaseModel):
    subject: str = Field(min_length=1, max_length=160)
    relation: str = Field(min_length=1, max_length=120)
    object: str = Field(min_length=1, max_length=160)


class TripletList(BaseModel):
    triplets: List[Triplet] = Field(default_factory=list)


@dataclass
class GraphRebuildResult:
    bot_id: str
    chunks_processed: int
    triplets_written: int
    errors: int


class KnowledgeGraphService:
    def __init__(self, db_path: str, llm_controller: Any):
        self.db_path = Path(db_path)
        self.llm_controller = llm_controller
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS triplets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    object TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(bot_id, source_id, subject, relation, object)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triplets_bot_id ON triplets(bot_id)")
            conn.commit()

    def rebuild_from_chunks(
        self,
        bot_id: str,
        chunks: List[Dict[str, Any]],
        clear_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
    ) -> GraphRebuildResult:
        chunks_processed = 0
        triplets_written = 0
        errors = 0
        total_chunks = len(chunks)

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                if clear_existing:
                    conn.execute("DELETE FROM triplets WHERE bot_id = ?", (bot_id,))

                for chunk in chunks:
                    chunks_processed += 1
                    source_id = str(chunk.get("source_id") or f"chunk_{chunks_processed}")
                    source_text = str(chunk.get("text") or "").strip()
                    if not source_text:
                        if progress_callback:
                            progress_callback(chunks_processed, total_chunks, triplets_written, errors)
                        continue

                    try:
                        extracted = self._extract_triplets(source_text)
                        if not extracted:
                            if progress_callback:
                                progress_callback(chunks_processed, total_chunks, triplets_written, errors)
                            continue
                        for t in extracted:
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO triplets (bot_id, source_id, subject, relation, object)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (bot_id, source_id, t.subject, t.relation, t.object),
                            )
                            triplets_written += 1
                    except Exception:
                        errors += 1
                    finally:
                        if progress_callback:
                            progress_callback(chunks_processed, total_chunks, triplets_written, errors)

                conn.commit()

        return GraphRebuildResult(
            bot_id=bot_id,
            chunks_processed=chunks_processed,
            triplets_written=triplets_written,
            errors=errors,
        )

    def get_graph_data(self, bot_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT subject, relation, object, source_id FROM triplets WHERE bot_id = ?",
                (bot_id,),
            ).fetchall()

        graph = nx.DiGraph()
        for subject, relation, obj, source_id in rows:
            graph.add_node(subject, label=subject)
            graph.add_node(obj, label=obj)
            graph.add_edge(subject, obj, label=relation, source_id=source_id)

        nodes = [{"id": node, "label": data.get("label", node)} for node, data in graph.nodes(data=True)]
        edges = [
            {
                "from": u,
                "to": v,
                "label": data.get("label", ""),
                "source_id": data.get("source_id", ""),
            }
            for u, v, data in graph.edges(data=True)
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "triplets": len(rows),
            },
        }

    def _extract_triplets(self, source_text: str) -> List[Triplet]:
        prompt = f"""
You are an information extraction engine.
Extract semantic relationships from the text as strict JSON.

Return ONLY this JSON object shape:
{{
  "triplets": [
    {{"subject": "entity", "relation": "relationship", "object": "entity"}}
  ]
}}

Rules:
- Keep relation concise and action-oriented.
- Do not invent facts not present in text.
- Ignore trivial entities.
- Max 8 triplets.

TEXT:
\"\"\"{source_text[:config.GRAPH_MAX_SOURCE_CHARS]}\"\"\"
""".strip()

        response = self.llm_controller.requests.post(
            f"{self.llm_controller.base_url}/api/generate",
            json={
                "model": self.llm_controller.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 300,
                },
            },
            timeout=min(int(self.llm_controller.timeout), 30),
        )
        response.raise_for_status()
        payload = response.json().get("response", "").strip()
        if not payload:
            return []

        data: Optional[Dict[str, Any]] = None
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            start = payload.find("{")
            end = payload.rfind("}")
            if start != -1 and end != -1 and end > start:
                data = json.loads(payload[start : end + 1])

        if not isinstance(data, dict):
            return []

        validated = TripletList.model_validate(data)
        cleaned: List[Triplet] = []
        for item in validated.triplets:
            subject = item.subject.strip()
            relation = item.relation.strip()
            obj = item.object.strip()
            if not subject or not relation or not obj:
                continue
            cleaned.append(Triplet(subject=subject, relation=relation, object=obj))
        return cleaned

