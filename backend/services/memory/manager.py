"""
JARVIS AI OS — Central Memory Manager.

Unified orchestrator consolidating:
- WorkingMemory: Sliding-window turns, active session, silent language.
- LongTermMemory: Persistent user facts, preferences, knowledge graph.
- EpisodicMemory: High-fidelity task execution traces, strategy confidence, workflows, lessons learned.
- SemanticMemory: Local/external document RAG, chunking, and citations.
"""

import os
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
    LessonLearned,
    SuccessfulWorkflow,
    UserPreference,
    Conversation,
    Message,
    CommandLog
)

from backend.services.memory.working_memory import WorkingMemory
from backend.services.memory.long_term_memory import LongTermMemory
from backend.services.memory.episodic_memory import EpisodicMemory
from backend.services.memory.semantic_memory import SemanticMemory
from backend.services.memory.types import MemoryType, MemoryItem, EpisodeRecord


class MemoryManager:
    """
    Unified Memory Manager providing a single, clean interface:
    - remember()
    - recall()
    - search()
    - update()
    - forget()
    - get_context()
    - store_episode()
    """

    def __init__(self):
        self._chroma_client = None
        self._conversations_collection = None
        self._knowledge_collection = None
        self._lessons_learned_collection = None
        self._workflows_collection = None
        self._db_engine = None
        self._session_factory = None
        self._initialized = False

        # Sub-memory modules
        self.working = WorkingMemory()
        self.long_term = LongTermMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()

    async def init(self) -> None:
        """Initialize ChromaDB collections, SQLite WAL database, and connect all sub-memories."""
        if self._initialized:
            return

        settings = get_settings()
        data_dir = settings.data_path

        # 1. Initialize ChromaDB
        try:
            os.environ["ANONYMIZED_TELEMETRY"] = "False"
            os.environ["CHROMA_TELEMETRY"] = "False"
            import chromadb
            from chromadb.config import Settings
            from chromadb.utils import embedding_functions

            chroma_path = str(data_dir / "chroma_data")
            try:
                self._chroma_client = chromadb.PersistentClient(
                    path=chroma_path,
                    settings=Settings(anonymized_telemetry=False)
                )
            except Exception as c_err:
                logger.debug("ChromaDB Settings notice: {}, creating default PersistentClient", c_err)
                self._chroma_client = chromadb.PersistentClient(path=chroma_path)

            try:
                emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            except Exception:
                logger.warning("SentenceTransformer not available, using default embeddings")
                emb_fn = embedding_functions.DefaultEmbeddingFunction()

            self._conversations_collection = self._chroma_client.get_or_create_collection(
                name="conversations",
                embedding_function=emb_fn,
                metadata={"description": "Conversation history for context retrieval"},
            )
            self._knowledge_collection = self._chroma_client.get_or_create_collection(
                name="knowledge",
                embedding_function=emb_fn,
                metadata={"description": "User knowledge, preferences, and facts"},
            )
            self._lessons_learned_collection = self._chroma_client.get_or_create_collection(
                name="lessons_learned",
                embedding_function=emb_fn,
                metadata={"description": "Learned corrections and error resolutions"},
            )
            self._workflows_collection = self._chroma_client.get_or_create_collection(
                name="successful_workflows",
                embedding_function=emb_fn,
                metadata={"description": "Successful action plans and execution patterns"},
            )

            logger.info("ChromaDB initialized at {}", chroma_path)
        except Exception as e:
            logger.error("Failed to initialize ChromaDB: {}", e)

        # 2. Initialize SQLite with WAL mode
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
            from backend.models.database import Base

            db_path = data_dir / "jarvis.db"
            db_url = f"sqlite+aiosqlite:///{db_path}"

            self._db_engine = create_async_engine(db_url, echo=False)
            self._session_factory = async_sessionmaker(self._db_engine, expire_on_commit=False)

            from sqlalchemy import text
            async with self._db_engine.begin() as conn:
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.run_sync(Base.metadata.create_all)

            logger.info("SQLite database initialized with WAL mode at {}", db_path)
        except Exception as e:
            logger.error("Failed to initialize SQLite: {}", e)

        # 3. Wire backends to sub-memories
        self.working.set_session_factory(self._session_factory)
        self.long_term.set_backends(
            session_factory=self._session_factory,
            knowledge_collection=self._knowledge_collection
        )
        self.episodic.set_backends(
            session_factory=self._session_factory,
            lessons_collection=self._lessons_learned_collection,
            workflows_collection=self._workflows_collection
        )
        self.semantic.set_chroma_client(self._chroma_client)

        self._initialized = True
        logger.info("MemoryManager fully initialized across Working, LongTerm, Episodic, and Semantic layers.")

    # ── High-Level Unified Interface ──────────────────────────────────────

    async def remember(self, content: str, metadata: Optional[dict] = None, memory_type: str = "long_term") -> str:
        """Store information in the appropriate memory layer."""
        if not self._initialized:
            await self.init()

        if memory_type == "working":
            role = (metadata or {}).get("role", "user")
            self.working.add_turn(role, content)
            return "stored_in_working_memory"
        elif memory_type == "episodic":
            meta = metadata or {}
            res = self.episodic.record_experience(
                goal=content,
                result=meta.get("result", ""),
                success=meta.get("success", True)
            )
            return res.get("id", "stored_in_episodic_memory")
        else:
            return await self.long_term.store_memory(content=content, metadata=metadata)

    async def recall(self, query: str, n_results: int = 5, memory_type: Optional[str] = None) -> list[dict]:
        """Recall relevant memories matching query from the specified or default layer."""
        if not self._initialized:
            await self.init()

        if memory_type == "semantic" or memory_type == "document":
            return self.semantic.search(query, top_k=n_results)
        elif memory_type == "episodic":
            return self.episodic.query_experiences(goal_query=query, limit=n_results)
        elif memory_type == "working":
            return self.working.get_turns()
        else:
            return await self.long_term.search_memories(query=query, n_results=n_results, memory_type=memory_type)

    async def search(self, query: str, n_results: int = 5, filter_type: Optional[str] = None) -> list[dict]:
        """Unified search across memory stores."""
        return await self.recall(query=query, n_results=n_results, memory_type=filter_type)

    async def update(self, memory_id: str, content: str, metadata: Optional[dict] = None) -> bool:
        """Update an existing memory item."""
        if not self._initialized:
            await self.init()
        # Delete old and store updated
        deleted = await self.long_term.delete_memory(memory_id)
        if deleted:
            await self.long_term.store_memory(content=content, metadata=metadata)
            return True
        return False

    async def forget(self, query_or_id: str) -> Dict[str, Any]:
        """Delete memories matching a query or specific ID."""
        if not self._initialized:
            await self.init()

        if query_or_id.startswith("mem_"):
            success = await self.long_term.delete_memory(query_or_id)
            return {"status": "success" if success else "error", "deleted_ids": [query_or_id] if success else []}
        return await self.long_term.forget_fact(query_or_id)

    async def get_context(self, query: str, max_items: int = 3) -> str:
        """Consolidate context from memory layers with non-blocking parallel lookups."""
        if not self._initialized:
            await self.init()

        context_parts = []

        # Fast non-blocking query tasks
        async def _query_lessons():
            if self._lessons_learned_collection:
                try:
                    count = await asyncio.to_thread(self._lessons_learned_collection.count)
                    if count > 0:
                        results = await asyncio.to_thread(
                            self._lessons_learned_collection.query,
                            query_texts=[query],
                            n_results=2
                        )
                        if results and results.get("documents") and results["documents"][0]:
                            return [f"- {doc}" for doc in results["documents"][0]]
                except Exception:
                    pass
            return []

        async def _query_workflows():
            if self._workflows_collection:
                try:
                    count = await asyncio.to_thread(self._workflows_collection.count)
                    if count > 0:
                        results = await asyncio.to_thread(
                            self._workflows_collection.query,
                            query_texts=[query],
                            n_results=1
                        )
                        if results and results.get("documents") and results["documents"][0]:
                            out = []
                            for i, doc in enumerate(results["documents"][0]):
                                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                                out.append(f"- {doc}")
                                if meta.get("opt_prompt"):
                                    out.append(f"  * Suggested Prompting: {meta['opt_prompt']}")
                            return out
                except Exception:
                    pass
            return []

        async def _query_knowledge():
            try:
                memories = await self.long_term.search_memories(query, n_results=max_items)
                if memories:
                    return [f"- {mem['content']}" for mem in memories]
            except Exception:
                pass
            return []

        # Query in parallel with a strict 0.5s timeout to guarantee instant response speed
        try:
            import asyncio
            lessons, workflows, knowledge = await asyncio.wait_for(
                asyncio.gather(_query_lessons(), _query_workflows(), _query_knowledge()),
                timeout=0.5
            )
            if lessons:
                context_parts.append("\n[PAST LESSONS & USER CORRECTIONS (MISTAKES TO AVOID)]")
                context_parts.extend(lessons)
            if workflows:
                context_parts.append("\n[REUSABLE WORKFLOWS & SUCCESSFUL STRATEGIES]")
                context_parts.extend(workflows)
            if knowledge:
                context_parts.append("\n[RELEVANT PREFERENCES & KNOWLEDGE]")
                context_parts.extend(knowledge)
        except Exception as e:
            logger.debug("Memory context gather note: {}", e)

        # Global structured preferences
        try:
            user_name = await self.long_term.get_user_preference("user_name")
            if user_name:
                context_parts.insert(0, f"User name: {user_name}")
        except Exception:
            pass

        # Silent language instruction
        try:
            lang_prompt = self.working.language.get_system_prompt_instruction()
            if lang_prompt:
                context_parts.insert(0, lang_prompt)
        except Exception:
            pass

        return "\n".join(context_parts) if context_parts else ""

    get_relevant_context = get_context

    def store_episode(
        self,
        goal: str,
        result: str = "",
        success: bool = True,
        plan: Optional[List[str]] = None,
        tools_used: Optional[List[str]] = None,
        execution_steps: Optional[List[Dict[str, Any]]] = None,
        execution_time_seconds: float = 0.0,
        failure_reason: Optional[str] = None,
        recovery_method: Optional[str] = None,
        alternative_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record task execution in episodic memory."""
        return self.episodic.record_experience(
            goal=goal,
            plan=plan,
            tools_used=tools_used,
            execution_steps=execution_steps,
            execution_time_seconds=execution_time_seconds,
            result=result,
            success=success,
            failure_reason=failure_reason,
            recovery_method=recovery_method,
            alternative_method=alternative_method
        )

    # ── Conversation Session Helpers ─────────────────────────────────────

    async def store_conversation(
        self, conversation_id: str, messages: list[dict], title: Optional[str] = None
    ) -> None:
        """Store conversation transcript in SQLite and ChromaDB."""
        if self._session_factory:
            try:
                async with self._session_factory() as session:
                    conv = Conversation(title=title or "Untitled Conversation")
                    session.add(conv)
                    await session.flush()
                    for msg in messages:
                        db_msg = DbMessage(
                            conversation_id=conv.id,
                            role=msg.get("role", "user"),
                            content=msg.get("content", ""),
                        )
                        session.add(db_msg)
                    await session.commit()
            except Exception as e:
                logger.error("Failed to store conversation in SQLite: {}", e)

        if self._conversations_collection:
            try:
                combined = "\n".join(
                    [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages]
                )
                if combined.strip():
                    self._conversations_collection.add(
                        documents=[combined[:2000]],
                        metadatas=[
                            {
                                "conversation_id": conversation_id,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "title": title or "Untitled",
                            }
                        ],
                        ids=[f"conv_{conversation_id}"],
                    )
            except Exception as e:
                logger.error("Failed to store conversation in ChromaDB: {}", e)

    # ── Background Self-Improvement & Analysis ───────────────────────────

    async def analyze_and_learn(self, conversation_id: str, messages: list[dict]) -> None:
        """Analyze completed conversation to extract preferences, lessons learned, and workflows."""
        if not messages:
            return

        try:
            logger.info("Brain analyzing conversation to extract corrections and preferences...")
            transcript = ""
            for m in messages[-10:]:
                role = m.get("role", "user").upper()
                content = m.get("content", "")
                transcript += f"{role}: {content}\n"

            from backend.services.llm import LLMService
            llm = LLMService()

            prompt = f"""You are the JARVIS Brain compiler. Analyze the following conversation transcript.
Identify:
1. Any explicit corrections the user made. Format as a list of objects with: "trigger" (what the user said), "error" (what was incorrect), and "correction" (the correct resolution).
2. Any successful workflow. Format as a list of objects with: "task" (what user wanted), "steps" (list of action descriptions), and "optimized_prompt" (optimized instruction for the future).
3. Any new facts or preferences about the user. Format as a list of objects with: "fact" (e.g., 'User prefers Google Chrome', 'User name is Ashrit'), "importance" ('low', 'medium', 'high', 'critical').

Return ONLY a valid JSON object matching this structure:
{{
  "corrections": [],
  "workflows": [],
  "preferences": []
}}

Transcript:
{transcript}
"""
            response_text = await llm.simple_completion(
                prompt=prompt,
                system_prompt="You are a strict data formatting compiler. Output raw JSON only.",
                max_tokens=1500,
                temperature=0.2
            )

            clean_json = response_text.strip()
            if clean_json.startswith("```"):
                lines = clean_json.split("\n")
                if lines[0].startswith("```"):
                    clean_json = "\n".join(lines[1:-1]).strip()

            analysis = json.loads(clean_json)

            # 1. Process user corrections
            for cor in analysis.get("corrections", []):
                trigger = cor.get("trigger", "")
                error_desc = cor.get("error", "")
                correction = cor.get("correction", "")
                if trigger and correction:
                    await self.episodic.store_lesson(trigger, error_desc, correction)

            # 2. Process successful workflows
            for wf in analysis.get("workflows", []):
                task = wf.get("task", "")
                steps = wf.get("steps", [])
                opt_prompt = wf.get("optimized_prompt", "")
                if task and steps:
                    await self.episodic.store_workflow(task, steps, opt_prompt)

            # 3. Process new facts/preferences
            for pref in analysis.get("preferences", []):
                fact = pref.get("fact", "")
                importance = pref.get("importance", "medium")
                if fact:
                    await self.long_term.store_memory(
                        content=fact,
                        metadata={"type": "preference", "importance": importance}
                    )

        except Exception as e:
            logger.error("Failed to analyze conversation: {}", e)

    # ── Pass-Through Compatibility Methods ────────────────────────────────

    async def store_memory(self, content: str, metadata: Optional[dict] = None) -> str:
        return await self.long_term.store_memory(content, metadata)

    async def search_memories(self, query: str, n_results: int = 5, memory_type: Optional[str] = None) -> list[dict]:
        return await self.long_term.search_memories(query, n_results, memory_type)

    async def delete_memory(self, memory_id: str) -> bool:
        return await self.long_term.delete_memory(memory_id)

    async def forget_fact(self, query: str) -> Dict[str, Any]:
        return await self.long_term.forget_fact(query)

    async def get_user_preference(self, key: str) -> Optional[str]:
        return await self.long_term.get_user_preference(key)

    async def set_user_preference(self, key: str, value: str) -> None:
        await self.long_term.set_user_preference(key, value)

    async def log_command(self, command: str, result: str, status: str = "success") -> None:
        await self.long_term.log_command(command, result, status)

    async def consolidate_memories(self) -> None:
        await self.long_term.consolidate_memories()

    async def create_conversation(self, title: str = "New Session") -> Optional[int]:
        return await self.working.create_conversation(title)

    async def add_message_to_conversation(self, conv_id: int, role: str, content: str) -> Optional[int]:
        return await self.working.add_message_to_conversation(conv_id, role, content)

    save_message = add_message_to_conversation
    add_message = add_message_to_conversation

    async def get_recent_conversations(self, limit: int = 30) -> list[dict]:
        return await self.working.get_recent_conversations(limit)

    async def get_conversation(self, conv_id: int) -> Optional[dict]:
        return await self.working.get_conversation(conv_id)

    async def rename_conversation(self, conv_id: int, new_title: str) -> bool:
        return await self.working.rename_conversation(conv_id, new_title)

    async def delete_conversation(self, conv_id: int) -> bool:
        return await self.working.delete_conversation(conv_id)

    async def generate_auto_title(self, conv_id: int, user_prompt: str, assistant_reply: str = "") -> str:
        return await self.working.generate_auto_title(conv_id, user_prompt, assistant_reply)

    @staticmethod
    def auto_generate_title(first_msg: str) -> str:
        return WorkingMemory.auto_generate_title(first_msg)

    async def shutdown(self) -> None:
        """Clean up database connections."""
        if self._db_engine:
            await self._db_engine.dispose()
        logger.info("MemoryManager shut down successfully")


# For 100% backward compatibility
MemoryService = MemoryManager
