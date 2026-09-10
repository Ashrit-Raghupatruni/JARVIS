"""
JARVIS AI OS — Long-Term Memory.

Manages persistent user facts, preferences, knowledge graph relationships,
and memory consolidation backed by ChromaDB and SQLite.
"""

import json
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from loguru import logger

from backend.config import get_settings
from backend.models.database import (
    MemoryLog,
    UserPreference,
    CommandLog
)

# NetworkX knowledge graph integration
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class LongTermMemory:
    """
    Long-Term Memory manages:
    1. Facts and user preferences (ChromaDB semantic search + SQLite MemoryLog).
    2. Structured key-value user preferences (UserPreference table).
    3. Knowledge Graph relationships (NetworkX DiGraph / JSON).
    4. Memory consolidation & deduplication.
    5. Command logs with sensitive masking.
    """

    def __init__(self, session_factory=None, knowledge_collection=None, data_dir: Optional[Path] = None):
        settings = get_settings()
        self.data_dir = data_dir or (settings.data_path / "memory")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_factory = session_factory
        self.knowledge_collection = knowledge_collection
        
        self.graph_path = self.data_dir / "knowledge_graph.json"
        self._init_knowledge_graph()
        logger.info("LongTermMemory initialized.")

    def set_backends(self, session_factory=None, knowledge_collection=None):
        if session_factory:
            self.session_factory = session_factory
        if knowledge_collection:
            self.knowledge_collection = knowledge_collection

    # ── Knowledge Graph Relationships ────────────────────────────────────

    def _init_knowledge_graph(self) -> None:
        if HAS_NETWORKX:
            self.graph = nx.DiGraph()
            if self.graph_path.exists():
                try:
                    with open(self.graph_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for node, attrs in data.get("nodes", {}).items():
                        self.graph.add_node(node, **attrs)
                    for edge in data.get("edges", []):
                        self.graph.add_edge(edge["source"], edge["target"], **edge.get("attrs", {}))
                    logger.debug("Knowledge graph memory loaded using NetworkX")
                except Exception as e:
                    logger.error("Failed to restore NetworkX graph: {}", e)
        else:
            self.graph = {"nodes": {}, "edges": []}
            if self.graph_path.exists():
                try:
                    with open(self.graph_path, "r", encoding="utf-8") as f:
                        self.graph = json.load(f)
                except Exception:
                    pass

    def save_knowledge_graph(self) -> None:
        try:
            if HAS_NETWORKX:
                data = {
                    "nodes": dict(self.graph.nodes(data=True)),
                    "edges": [
                        {"source": u, "target": v, "attrs": d} 
                        for u, v, d in self.graph.edges(data=True)
                    ]
                }
            else:
                data = self.graph

            with open(self.graph_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save knowledge graph: {}", e)

    def add_relationship(self, entity_a: str, relationship: str, entity_b: str) -> None:
        """Insert relationship node/edge into the Knowledge Graph."""
        if HAS_NETWORKX:
            self.graph.add_node(entity_a, type="entity")
            self.graph.add_node(entity_b, type="entity")
            self.graph.add_edge(entity_a, entity_b, relationship=relationship)
        else:
            self.graph["nodes"][entity_a] = {"type": "entity"}
            self.graph["nodes"][entity_b] = {"type": "entity"}
            self.graph["edges"].append({
                "source": entity_a,
                "target": entity_b,
                "attrs": {"relationship": relationship}
            })
        self.save_knowledge_graph()

    def get_related_entities(self, entity: str) -> List[str]:
        """Fetch all related entities connected to a node."""
        if HAS_NETWORKX:
            if entity in self.graph:
                return list(self.graph.neighbors(entity))
        else:
            neighbors = []
            for edge in self.graph.get("edges", []):
                if edge["source"] == entity:
                    neighbors.append(edge["target"])
            return neighbors
        return []

    # ── Facts and Semantic Knowledge ─────────────────────────────────────

    async def store_memory(self, content: str, metadata: Optional[dict] = None) -> str:
        """Store a fact or preference in ChromaDB and SQLite."""
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        meta = metadata or {}
        meta["timestamp"] = datetime.now(timezone.utc).isoformat()
        importance = meta.get("importance", "medium")

        # Store in ChromaDB
        if self.knowledge_collection:
            try:
                self.knowledge_collection.add(
                    documents=[content],
                    metadatas=[meta],
                    ids=[memory_id],
                )
            except Exception as e:
                logger.error("ChromaDB store error: {}", e)

        # Store in SQLite MemoryLog
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    log = MemoryLog(
                        id=memory_id,
                        content=content,
                        importance=importance,
                        is_consolidated=0
                    )
                    session.add(log)
                    await session.commit()
            except Exception as e:
                logger.error("SQLite MemoryLog store error: {}", e)

        logger.info("Stored memory '{}' (importance={}): {}...", memory_id, importance, content[:80])
        return memory_id

    remember = store_memory

    async def search_memories(
        self, query: str, n_results: int = 5, memory_type: Optional[str] = None
    ) -> list[dict]:
        """Search memories using semantic similarity in ChromaDB."""
        if not self.knowledge_collection or self.knowledge_collection.count() == 0:
            return []

        try:
            where_filter = {"type": memory_type} if memory_type else None
            results = self.knowledge_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )

            memories = []
            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    memory = {
                        "content": doc,
                        "id": results["ids"][0][i] if results["ids"] else None,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results.get("distances") else None,
                    }
                    memories.append(memory)
            return memories
        except Exception as e:
            logger.error("Memory search failed: {}", e)
            return []

    recall = search_memories

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete memory by ID from ChromaDB and SQLite."""
        deleted = False
        try:
            if self.knowledge_collection:
                self.knowledge_collection.delete(ids=[memory_id])
                deleted = True
            if self.session_factory:
                async with self.session_factory() as session:
                    res = await session.execute(select(MemoryLog).where(MemoryLog.id == memory_id))
                    m = res.scalar_one_or_none()
                    if m:
                        await session.delete(m)
                        await session.commit()
                        deleted = True
            return deleted
        except Exception as e:
            logger.error("Failed to delete memory '{}': {}", memory_id, e)
            return False

    async def forget_fact(self, query: str) -> Dict[str, Any]:
        """Find and delete memories matching a semantic search query."""
        if not self.knowledge_collection or self.knowledge_collection.count() == 0:
            return {"status": "success", "deleted_count": 0, "message": "No memories found to delete."}

        try:
            results = self.knowledge_collection.query(
                query_texts=[query],
                n_results=5
            )
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]
            if not ids:
                return {"status": "success", "deleted_count": 0, "message": f"No memories found matching '{query}'."}

            deleted_ids = []
            for mid in ids:
                if await self.delete_memory(mid):
                    deleted_ids.append(mid)

            return {
                "status": "success",
                "deleted_count": len(deleted_ids),
                "deleted_ids": deleted_ids,
                "deleted_facts": docs[:len(deleted_ids)],
                "message": f"Successfully deleted {len(deleted_ids)} memory item(s) matching '{query}'."
            }
        except Exception as e:
            logger.error("Error in forget_fact: {}", e)
            return {"status": "error", "error": str(e)}

    # ── User Preferences ─────────────────────────────────────────────────

    async def get_user_preference(self, key: str) -> Optional[str]:
        if not self.session_factory:
            return None
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(UserPreference).where(UserPreference.key == key)
                )
                pref = result.scalar_one_or_none()
                return pref.value if pref else None
        except Exception as e:
            logger.error("Failed to get preference '{}': {}", key, e)
            return None

    async def set_user_preference(self, key: str, value: str) -> None:
        if not self.session_factory:
            return
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(UserPreference).where(UserPreference.key == key)
                )
                pref = result.scalar_one_or_none()
                if pref:
                    pref.value = value
                    pref.updated_at = datetime.now(timezone.utc)
                else:
                    pref = UserPreference(key=key, value=value)
                    session.add(pref)
                await session.commit()
        except Exception as e:
            logger.error("Failed to set preference '{}': {}", key, e)

    # ── Command Execution Logging ─────────────────────────────────────────

    async def log_command(self, command: str, result: str, status: str = "success") -> None:
        if not self.session_factory:
            return
        try:
            from backend.services.safety import mask_sensitive_data
            masked_command = mask_sensitive_data(command)
            masked_result = mask_sensitive_data(result[:2000])

            async with self.session_factory() as session:
                log = CommandLog(command=masked_command, result=masked_result, status=status)
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error("Failed to log command: {}", e)

    # ── Memory Consolidation ─────────────────────────────────────────────

    async def consolidate_memories(self) -> None:
        """Consolidate duplicate/overlapping memories using LLM merge."""
        if not self.session_factory:
            return

        try:
            logger.info("Starting long-term memory consolidation...")
            async with self.session_factory() as session:
                result = await session.execute(
                    select(MemoryLog).where(
                        MemoryLog.is_consolidated == 0,
                        MemoryLog.importance != "critical"
                    )
                )
                unconsolidated = result.scalars().all()

            if len(unconsolidated) < 3:
                logger.info("Not enough unconsolidated memories to run merge.")
                return

            consolidated_ids = []
            for mem in unconsolidated:
                if mem.id in consolidated_ids:
                    continue

                similar = await self.search_memories(mem.content, n_results=4)
                similar_hits = [
                    h for h in similar 
                    if h["id"] != mem.id and h["distance"] is not None and h["distance"] < 0.35
                ]

                if not similar_hits:
                    continue

                memories_to_merge = [mem.content] + [h["content"] for h in similar_hits]
                ids_to_merge = [mem.id] + [h["id"] for h in similar_hits]

                from backend.services.llm import LLMService
                llm = LLMService()

                prompt = f"""You are the JARVIS memory consolidation agent.
Merge the following overlapping facts/preferences into a single clear, concise statement.
Do not lose specific details (names, emails, browsers, paths).

Statements to merge:
{chr(10).join([f'- {m}' for m in memories_to_merge])}

Return ONLY the single consolidated statement text.
"""
                merged_statement = await llm.simple_completion(prompt)
                merged_statement = merged_statement.strip()

                await self.store_memory(
                    content=merged_statement,
                    metadata={"type": "preference", "importance": "medium", "consolidated": "true"}
                )

                async with self.session_factory() as session:
                    for old_id in ids_to_merge:
                        result = await session.execute(
                            select(MemoryLog).where(MemoryLog.id == old_id)
                        )
                        db_mem = result.scalar_one_or_none()
                        if db_mem:
                            db_mem.is_consolidated = 1
                    await session.commit()

                if self.knowledge_collection:
                    try:
                        self.knowledge_collection.delete(ids=ids_to_merge)
                    except Exception:
                        pass

                consolidated_ids.extend(ids_to_merge)
                logger.info("Consolidated {} memories into: {}", len(ids_to_merge), merged_statement)

        except Exception as e:
            logger.error("Failed to consolidate memories: {}", e)
