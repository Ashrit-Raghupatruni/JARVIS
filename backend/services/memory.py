"""
Memory service for JARVIS.

Provides persistent memory using ChromaDB for semantic vector search
and SQLite for structured data storage (conversations, preferences, command logs,
and self-improving brain analytics).
"""

import json
import uuid
from datetime import datetime, timezone
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


class MemoryService:
    """Service for persistent memory, context retrieval, and self-improvement."""

    def __init__(self):
        self._chroma_client = None
        self._conversations_collection = None
        self._knowledge_collection = None
        self._lessons_learned_collection = None
        self._workflows_collection = None
        self._db_engine = None
        self._session_factory = None
        self._initialized = False

    async def init(self) -> None:
        """Initialize ChromaDB collections and SQLAlchemy engine."""
        settings = get_settings()
        data_dir = settings.data_path

        # Initialize ChromaDB
        try:
            import os
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

            # Use sentence-transformers for embeddings
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

            logger.info(f"ChromaDB initialized at {chroma_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

        # Initialize SQLite
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

            logger.info(f"SQLite database initialized with WAL mode at {db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")

        self._initialized = True
        logger.info("Memory service fully initialized with Self-Improving Brain capacity")

    async def store_memory(self, content: str, metadata: Optional[dict] = None) -> str:
        """Store a fact or preference in ChromaDB and SQLite."""
        if not self._knowledge_collection:
            return "Memory storage not available"

        try:
            memory_id = f"mem_{uuid.uuid4().hex[:12]}"
            meta = metadata or {}
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            importance = meta.get("importance", "medium")

            # Store in ChromaDB
            self._knowledge_collection.add(
                documents=[content],
                metadatas=[meta],
                ids=[memory_id],
            )

            # Store in SQLite MemoryLog
            if self._session_factory:
                async with self._session_factory() as session:
                    log = MemoryLog(
                        id=memory_id,
                        content=content,
                        importance=importance,
                        is_consolidated=0
                    )
                    session.add(log)
                    await session.commit()

            logger.info(f"Stored memory '{memory_id}' (importance={importance}): {content[:80]}...")
            return memory_id
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return f"Error storing memory: {str(e)}"

    async def search_memories(
        self, query: str, n_results: int = 5, memory_type: Optional[str] = None
    ) -> list[dict]:
        """Search memories using semantic similarity in ChromaDB."""
        if not self._knowledge_collection or self._knowledge_collection.count() == 0:
            return []

        try:
            where_filter = {"type": memory_type} if memory_type else None
            results = self._knowledge_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )

            memories = []
            if results and results["documents"] and results["documents"][0]:
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
            logger.error(f"Memory search failed: {e}")
            return []

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory by ID from both ChromaDB and SQLite."""
        deleted = False
        try:
            if self._knowledge_collection:
                self._knowledge_collection.delete(ids=[memory_id])
                deleted = True
                logger.info(f"Deleted memory '{memory_id}' from ChromaDB knowledge collection")
            if self._session_factory:
                from sqlalchemy import select
                async with self._session_factory() as session:
                    res = await session.execute(select(MemoryLog).where(MemoryLog.id == memory_id))
                    m = res.scalar_one_or_none()
                    if m:
                        await session.delete(m)
                        await session.commit()
                        deleted = True
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete memory '{memory_id}': {e}")
            return False

    async def forget_fact(self, query: str) -> Dict[str, Any]:
        """Find and delete memories matching a semantic search query."""
        if not self._knowledge_collection or self._knowledge_collection.count() == 0:
            return {"status": "success", "deleted_count": 0, "message": "No memories found to delete."}

        try:
            results = self._knowledge_collection.query(
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
            logger.error(f"Error in forget_fact: {e}")
            return {"status": "error", "error": str(e)}

    async def get_user_preference(self, key: str) -> Optional[str]:
        """Get user preference by key from SQLite."""
        if not self._session_factory:
            return None

        try:
            from sqlalchemy import select
            async with self._session_factory() as session:
                result = await session.execute(
                    select(UserPreference).where(UserPreference.key == key)
                )
                pref = result.scalar_one_or_none()
                return pref.value if pref else None
        except Exception as e:
            logger.error(f"Failed to get preference '{key}': {e}")
            return None

    async def set_user_preference(self, key: str, value: str) -> None:
        """Set or update user preference in SQLite."""
        if not self._session_factory:
            return

        try:
            from sqlalchemy import select
            async with self._session_factory() as session:
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
                logger.info(f"User preference set: {key}={value[:50]}")
        except Exception as e:
            logger.error(f"Failed to set preference '{key}': {e}")

    async def store_conversation(
        self, conversation_id: str, messages: list[dict], title: Optional[str] = None
    ) -> None:
        """Store conversation in SQLite and ChromaDB."""
        if self._session_factory:
            try:
                from backend.models.database import Conversation, Message as DbMessage
                async with self._session_factory() as session:
                    conv = Conversation(
                        title=title or "Untitled Conversation",
                    )
                    session.add(conv)
                    await session.flush()  # Generates conv.id
                    
                    for msg in messages:
                        db_msg = DbMessage(
                            conversation_id=conv.id,
                            role=msg.get("role", "user"),
                            content=msg.get("content", ""),
                        )
                        session.add(db_msg)
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to store conversation in SQLite: {e}")

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
                logger.error(f"Failed to store conversation in ChromaDB: {e}")

    async def create_conversation(self, title: str = "New Session") -> Optional[int]:
        """Explicitly create a new conversation session in SQLite."""
        if not self._session_factory:
            return None
        try:
            from backend.models.database import Conversation
            async with self._session_factory() as session:
                conv = Conversation(title=title)
                session.add(conv)
                await session.commit()
                await session.refresh(conv)
                return conv.id
        except Exception as e:
            logger.error(f"Failed to create conversation session: {e}")
            return None

    async def add_message_to_conversation(
        self, conv_id: int, role: str, content: str
    ) -> Optional[int]:
        """Append a single message in real-time to a conversation in SQLite."""
        if not self._session_factory:
            return None
        try:
            from backend.models.database import Conversation, Message as DbMessage
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                conv = result.scalar_one_or_none()
                if not conv:
                    conv = Conversation(id=conv_id, title="New Conversation")
                    session.add(conv)
                    await session.flush()
                
                conv.updated_at = datetime.now(timezone.utc)
                msg = DbMessage(
                    conversation_id=conv.id,
                    role=role,
                    content=content,
                )
                session.add(msg)
                await session.commit()
                await session.refresh(msg)
                return conv.id
        except Exception as e:
            logger.error(f"Failed to append message to conversation {conv_id}: {e}")
            return None

    save_message = add_message_to_conversation
    add_message = add_message_to_conversation

    async def generate_auto_title(
        self, conv_id: int, user_prompt: str, assistant_reply: str = ""
    ) -> str:
        """Generate a short (3-6 word) title using a cheap LLM call, with truncated text fallback."""
        fallback_title = user_prompt.strip().replace("\n", " ")[:40] or "New Conversation"
        if len(fallback_title) == 40:
            fallback_title += "..."

        title = fallback_title
        try:
            from backend.services.manager import ServiceManager
            llm_svc = ServiceManager.get_instance("llm_service")
            if llm_svc and hasattr(llm_svc, "simple_completion"):
                sys_prompt = "You are a concise title generator. Generate a short 3-6 word title summarizing the user prompt. Output ONLY the plain text title. No quotes, no markdown, no punctuation."
                llm_response = await llm_svc.simple_completion(f"User Prompt: {user_prompt[:200]}", system_prompt=sys_prompt)
                if llm_response and isinstance(llm_response, str):
                    clean_t = llm_response.strip().strip('"\'`')
                    if 2 <= len(clean_t) <= 60:
                        title = clean_t
        except Exception as e:
            logger.warning(f"LLM auto-title generation notice for conv {conv_id}: {e}")

        # Update in DB
        if self._session_factory:
            try:
                from backend.models.database import Conversation
                async with self._session_factory() as session:
                    result = await session.execute(
                        select(Conversation).where(Conversation.id == conv_id)
                    )
                    conv = result.scalar_one_or_none()
                    if conv:
                        conv.title = title
                        conv.updated_at = datetime.now(timezone.utc)
                        await session.commit()
                        logger.info("✓ Auto-generated title for conv {}: '{}'", conv_id, title)
            except Exception as db_err:
                logger.error(f"Failed to save auto-generated title to DB: {db_err}")

        return title

    async def get_recent_conversations(self, limit: int = 30) -> list[dict]:
        """Get recent conversations from SQLite ordered by last updated."""
        if not self._session_factory:
            return []

        try:
            from sqlalchemy import select
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Conversation)
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                )
                conversations = result.scalars().all()
                return [
                    {
                        "id": c.id,
                        "title": c.title,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                        "message_count": len(c.messages) if c.messages else 0
                    }
                    for c in conversations
                ]
        except Exception as e:
            logger.error(f"Failed to get recent conversations: {e}")
            return []

    async def get_conversation(self, conv_id: int) -> Optional[dict]:
        """Get a single conversation with full message transcript by ID."""
        if not self._session_factory:
            return None

        try:
            from sqlalchemy import select
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                c = result.scalar_one_or_none()
                if not c:
                    return None
                return {
                    "id": c.id,
                    "title": c.title,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "messages": [
                        {
                            "id": m.id,
                            "role": m.role,
                            "content": m.content,
                            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                        }
                        for m in (c.messages or [])
                    ]
                }
        except Exception as e:
            logger.error(f"Failed to get conversation {conv_id}: {e}")
            return None

    async def rename_conversation(self, conv_id: int, new_title: str) -> bool:
        """Rename a conversation in SQLite."""
        if not self._session_factory:
            return False

        try:
            from sqlalchemy import select
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                c = result.scalar_one_or_none()
                if not c:
                    return False
                c.title = new_title.strip()
                await session.commit()
                logger.info(f"Renamed conversation {conv_id} to '{new_title.strip()}'")
                return True
        except Exception as e:
            logger.error(f"Failed to rename conversation {conv_id}: {e}")
            return False

    async def delete_conversation(self, conv_id: int) -> bool:
        """Delete a conversation and its messages from SQLite."""
        if not self._session_factory:
            return False

        try:
            from sqlalchemy import select
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                c = result.scalar_one_or_none()
                if not c:
                    return False
                await session.delete(c)
                await session.commit()
                logger.info(f"Deleted conversation {conv_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete conversation {conv_id}: {e}")
            return False

    @staticmethod
    def auto_generate_title(first_msg: str) -> str:
        """Auto-generate a 3-6 word title from initial user message."""
        clean = first_msg.strip()
        if not clean:
            return "New Conversation"
        words = clean.split()
        if len(words) <= 6:
            return clean.capitalize()
        return " ".join(words[:6]).capitalize() + "..."

    async def log_command(self, command: str, result: str, status: str = "success") -> None:
        """Log a command execution to SQLite."""
        if not self._session_factory:
            return

        try:
            from backend.services.safety import mask_sensitive_data
            masked_command = mask_sensitive_data(command)
            masked_result = mask_sensitive_data(result[:2000])

            async with self._session_factory() as session:
                log = CommandLog(command=masked_command, result=masked_result, status=status)
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log command: {e}")

    async def analyze_and_learn(self, conversation_id: str, messages: list[dict]) -> None:
        """
        Analyze a completed conversation to extract preferences, lessons learned, and workflows.
        This runs as an asynchronous background task so it doesn't block the user.
        """
        if not messages:
            return

        try:
            logger.info("Brain analyzing conversation to extract corrections and preferences...")
            
            # Combine transcript
            transcript = ""
            for m in messages[-10:]:  # Check last 10 messages for focus
                role = m.get("role", "user").upper()
                content = m.get("content", "")
                transcript += f"{role}: {content}\n"

            # Dynamic local import to prevent circular import loops
            from backend.services.llm import LLMService
            llm = LLMService()

            prompt = f"""You are the JARVIS Brain compiler. Analyze the following conversation transcript.
Identify:
1. Any explicit corrections the user made (e.g. correcting a tool choice, setting, path name, or behavior). Format as a list of objects with: "trigger" (what the user said), "error" (what was incorrect), and "correction" (the correct resolution).
2. Any successful workflow (e.g. user requested a sequence of actions that succeeded). Format as a list of objects with: "task" (what user wanted), "steps" (list of action descriptions), and "optimized_prompt" (optimized instruction for the future).
3. Any new facts or preferences about the user. Format as a list of objects with: "fact" (e.g., 'User prefers Google Chrome', 'User name is Ashrit'), "importance" ('low', 'medium', 'high', 'critical').

Return ONLY a valid JSON object matching this structure (no other text, no markdown code block formatting, just the raw JSON):
{{
  "corrections": [],
  "workflows": [],
  "preferences": []
}}

Transcript:
{transcript}
"""
            # Run simple completion
            response_text = await llm.simple_completion(
                prompt=prompt,
                system_prompt="You are a strict data formatting compiler. Output raw JSON only.",
                max_tokens=1500,
                temperature=0.2
            )

            # Clean markdown code wrappers if model returned them
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
                    lesson_id = f"lesson_{uuid.uuid4().hex[:12]}"
                    # Save to ChromaDB
                    if self._lessons_learned_collection:
                        content_str = f"Trigger: {trigger} | Error: {error_desc} | Correction: {correction}"
                        self._lessons_learned_collection.add(
                            documents=[content_str],
                            metadatas=[{"trigger": trigger, "correction": correction}],
                            ids=[lesson_id]
                        )
                    # Save to SQLite
                    if self._session_factory:
                        async with self._session_factory() as session:
                            lesson = LessonLearned(
                                id=lesson_id,
                                trigger_keywords=trigger,
                                error_description=error_desc,
                                correction=correction
                            )
                            session.add(lesson)
                            await session.commit()
                    logger.info(f"Learned a new lesson: {correction[:50]}...")

            # 2. Process successful workflows
            for wf in analysis.get("workflows", []):
                task = wf.get("task", "")
                steps = wf.get("steps", [])
                opt_prompt = wf.get("optimized_prompt", "")

                if task and steps:
                    wf_id = f"wf_{uuid.uuid4().hex[:12]}"
                    steps_str = json.dumps(steps)
                    # Save to ChromaDB
                    if self._workflows_collection:
                        content_str = f"Task: {task} | Steps: {steps_str}"
                        self._workflows_collection.add(
                            documents=[content_str],
                            metadatas=[{"task": task, "opt_prompt": opt_prompt}],
                            ids=[wf_id]
                        )
                    # Save to SQLite
                    if self._session_factory:
                        async with self._session_factory() as session:
                            workflow = SuccessfulWorkflow(
                                id=wf_id,
                                task_description=task,
                                steps_json=steps_str,
                                optimized_prompt=opt_prompt
                            )
                            session.add(workflow)
                            await session.commit()
                    logger.info(f"Saved successful workflow for: {task[:50]}...")

            # 3. Process new facts/preferences
            for pref in analysis.get("preferences", []):
                fact = pref.get("fact", "")
                importance = pref.get("importance", "medium")

                if fact:
                    await self.store_memory(
                        content=fact,
                        metadata={"type": "preference", "importance": importance}
                    )

        except Exception as e:
            logger.error(f"Failed to analyze conversation and extract knowledge: {e}")

    async def get_relevant_context(self, query: str, max_items: int = 3) -> str:
        """
        Query ChromaDB knowledge, lessons learned, and successful workflows,
        returning a consolidated context injection block for the LLM.
        """
        context_parts = []

        # 1. Lessons Learned / Corrections
        if self._lessons_learned_collection and self._lessons_learned_collection.count() > 0:
            try:
                results = self._lessons_learned_collection.query(
                    query_texts=[query], n_results=2
                )
                if results and results["documents"] and results["documents"][0]:
                    context_parts.append("\n[PAST LESSONS & USER CORRECTIONS (MISTAKES TO AVOID)]")
                    for doc in results["documents"][0]:
                        context_parts.append(f"- {doc}")
            except Exception as e:
                logger.error(f"Error querying lessons learned: {e}")

        # 2. Successful Workflows
        if self._workflows_collection and self._workflows_collection.count() > 0:
            try:
                results = self._workflows_collection.query(
                    query_texts=[query], n_results=1
                )
                if results and results["documents"] and results["documents"][0]:
                    context_parts.append("\n[REUSABLE WORKFLOWS & SUCCESSFUL STRATEGIES]")
                    for i, doc in enumerate(results["documents"][0]):
                        meta = results["metadatas"][0][i] if results["metadatas"] else {}
                        context_parts.append(f"- {doc}")
                        if meta.get("opt_prompt"):
                            context_parts.append(f"  * Suggested Prompting: {meta['opt_prompt']}")
            except Exception as e:
                logger.error(f"Error querying successful workflows: {e}")

        # 3. General Knowledge/Memories
        memories = await self.search_memories(query, n_results=max_items)
        if memories:
            context_parts.append("\n[RELEVANT PREFERENCES & KNOWLEDGE]")
            for mem in memories:
                context_parts.append(f"- {mem['content']}")

        # 3b. Past Conversations (Inter-session continuity)
        if self._conversations_collection and self._conversations_collection.count() > 0:
            try:
                c_results = self._conversations_collection.query(
                    query_texts=[query], n_results=2
                )
                if c_results and c_results.get("documents") and c_results["documents"][0]:
                    context_parts.append("\n[RELEVANT PAST CONVERSATIONS]")
                    for doc in c_results["documents"][0]:
                        context_parts.append(f"- {doc[:250]}...")
            except Exception as ce:
                logger.debug(f"Error querying conversation history: {ce}")

        # 4. Global structured preferences
        user_name = await self.get_user_preference("user_name")
        if user_name:
            context_parts.insert(0, f"User name: {user_name}")

        if context_parts:
            return "\n".join(context_parts)
        return ""

    async def consolidate_memories(self) -> None:
        """
        Consolidate duplicate/overlapping memories to keep vector storage compact.
        Finds unconsolidated low/medium priority memories, merges them using the LLM,
        and deletes redundant logs. Shielding 'critical' memories from changes.
        """
        if not self._session_factory:
            return

        try:
            logger.info("Starting memory consolidation process...")
            from sqlalchemy import select
            
            # Fetch all non-critical, unconsolidated memories
            async with self._session_factory() as session:
                result = await session.execute(
                    select(MemoryLog).where(
                        MemoryLog.is_consolidated == 0,
                        MemoryLog.importance != "critical"
                    )
                )
                unconsolidated = result.scalars().all()

            if len(unconsolidated) < 3:
                logger.info("Not enough unconsolidated memories to run merge. Skipping.")
                return

            # Group them by similarity using ChromaDB queries
            consolidated_ids = []
            for mem in unconsolidated:
                if mem.id in consolidated_ids:
                    continue

                # Query ChromaDB for memories similar to this one
                similar = await self.search_memories(mem.content, n_results=4)
                # Keep only those close in distance (e.g. distance < 0.35)
                similar_hits = [
                    h for h in similar 
                    if h["id"] != mem.id and h["distance"] is not None and h["distance"] < 0.35
                ]

                if not similar_hits:
                    continue

                # We have overlapping memories! Summarize/merge them using LLM
                memories_to_merge = [mem.content] + [h["content"] for h in similar_hits]
                ids_to_merge = [mem.id] + [h["id"] for h in similar_hits]

                from backend.services.llm import LLMService
                llm = LLMService()

                prompt = f"""You are the JARVIS memory consolidation agent.
Merge the following overlapping facts/preferences into a single clear, concise statement.
Do not lose any specific details (like specific names, emails, browsers, or folder paths).

Statements to merge:
{chr(10).join([f'- {m}' for m in memories_to_merge])}

Return ONLY the single consolidated statement text. No conversational text or markdown code wrappers.
"""
                merged_statement = await llm.simple_completion(prompt)
                merged_statement = merged_statement.strip()

                # Save the new consolidated memory
                new_id = await self.store_memory(
                    content=merged_statement,
                    metadata={"type": "preference", "importance": "medium", "consolidated": "true"}
                )

                # Mark all old ones as consolidated in SQLite and delete from ChromaDB
                async with self._session_factory() as session:
                    for old_id in ids_to_merge:
                        result = await session.execute(
                            select(MemoryLog).where(MemoryLog.id == old_id)
                        )
                        db_mem = result.scalar_one_or_none()
                        if db_mem:
                            db_mem.is_consolidated = 1
                    await session.commit()

                # Delete from ChromaDB
                if self._knowledge_collection:
                    try:
                        self._knowledge_collection.delete(ids=ids_to_merge)
                    except Exception:
                        pass

                consolidated_ids.extend(ids_to_merge)
                logger.info(f"Successfully consolidated {len(ids_to_merge)} memories into: {merged_statement}")

        except Exception as e:
            logger.error(f"Failed to consolidate memories: {e}")

    async def shutdown(self) -> None:
        """Clean up database engine connections."""
        if self._db_engine:
            await self._db_engine.dispose()
        logger.info("Memory service shut down successfully")
