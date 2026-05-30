"""
Memory service for JARVIS.

Provides persistent memory using ChromaDB for semantic vector search
and SQLite for structured data storage (conversations, preferences, command logs).
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from backend.config import get_settings


class MemoryService:
    """Service for persistent memory and context retrieval."""

    def __init__(self):
        self._chroma_client = None
        self._conversations_collection = None
        self._knowledge_collection = None
        self._db_engine = None
        self._session_factory = None
        self._initialized = False

    async def init(self) -> None:
        """Initialize ChromaDB and SQLite storage."""
        settings = get_settings()
        data_dir = settings.data_path

        # Initialize ChromaDB
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            chroma_path = str(data_dir / "chroma_data")
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

            async with self._db_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info(f"SQLite database initialized at {db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")

        self._initialized = True
        logger.info("Memory service fully initialized")

    async def store_memory(self, content: str, metadata: Optional[dict] = None) -> str:
        """
        Store a piece of knowledge/memory in the vector database.

        Args:
            content: The text content to remember.
            metadata: Optional metadata dict (e.g. {"type": "preference"}).

        Returns:
            The memory ID.
        """
        if not self._knowledge_collection:
            return "Memory storage not available"

        try:
            memory_id = f"mem_{uuid.uuid4().hex[:12]}"
            meta = metadata or {}
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()

            self._knowledge_collection.add(
                documents=[content],
                metadatas=[meta],
                ids=[memory_id],
            )

            logger.info(f"Stored memory '{memory_id}': {content[:80]}...")
            return memory_id
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return f"Error storing memory: {str(e)}"

    async def search_memories(
        self, query: str, n_results: int = 5, memory_type: Optional[str] = None
    ) -> list[dict]:
        """
        Search memories using semantic similarity.

        Args:
            query: Search query text.
            n_results: Maximum number of results.
            memory_type: Optional filter by metadata type.

        Returns:
            List of matching memories with content and metadata.
        """
        if not self._knowledge_collection:
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
                        "metadata": (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                        "distance": (
                            results["distances"][0][i] if results.get("distances") else None
                        ),
                    }
                    memories.append(memory)

            logger.debug(f"Memory search for '{query}': {len(memories)} results")
            return memories
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    async def get_user_preference(self, key: str) -> Optional[str]:
        """Get a user preference by key from SQLite."""
        if not self._session_factory:
            return None

        try:
            from sqlalchemy import select

            from backend.models.database import UserPreference

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
        """Set or update a user preference in SQLite."""
        if not self._session_factory:
            return

        try:
            from sqlalchemy import select

            from backend.models.database import UserPreference

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
        """Store a conversation in both SQLite and ChromaDB for context retrieval."""
        # Store in SQLite
        if self._session_factory:
            try:
                from backend.models.database import Conversation, Message

                async with self._session_factory() as session:
                    conv = Conversation(
                        id=conversation_id,
                        title=title or "Untitled Conversation",
                    )
                    session.add(conv)

                    for msg in messages:
                        db_msg = Message(
                            conversation_id=conversation_id,
                            role=msg.get("role", "user"),
                            content=msg.get("content", ""),
                        )
                        session.add(db_msg)

                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to store conversation in SQLite: {e}")

        # Store in ChromaDB for semantic search
        if self._conversations_collection:
            try:
                # Combine messages into a single document
                combined = "\n".join(
                    [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages]
                )
                if combined.strip():
                    self._conversations_collection.add(
                        documents=[combined[:2000]],  # Limit size
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

    async def get_recent_conversations(self, limit: int = 10) -> list[dict]:
        """Get recent conversations from SQLite."""
        if not self._session_factory:
            return []

        try:
            from sqlalchemy import select

            from backend.models.database import Conversation

            async with self._session_factory() as session:
                result = await session.execute(
                    select(Conversation)
                    .order_by(Conversation.created_at.desc())
                    .limit(limit)
                )
                conversations = result.scalars().all()
                return [
                    {
                        "id": c.id,
                        "title": c.title,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in conversations
                ]
        except Exception as e:
            logger.error(f"Failed to get recent conversations: {e}")
            return []

    async def log_command(self, command: str, result: str, status: str = "success") -> None:
        """Log a command execution to SQLite."""
        if not self._session_factory:
            return

        try:
            from backend.models.database import CommandLog

            async with self._session_factory() as session:
                log = CommandLog(command=command, result=result[:2000], status=status)
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log command: {e}")

    async def get_relevant_context(self, query: str, max_items: int = 3) -> str:
        """
        Get relevant context for a user query by searching both
        knowledge and conversation history.

        Args:
            query: The user's current query.
            max_items: Maximum number of context items to return.

        Returns:
            Formatted context string to inject into LLM prompt.
        """
        context_parts = []

        # Search knowledge/memories
        memories = await self.search_memories(query, n_results=max_items)
        if memories:
            context_parts.append("**Relevant memories:**")
            for mem in memories:
                context_parts.append(f"- {mem['content']}")

        # Search conversation history
        if self._conversations_collection:
            try:
                results = self._conversations_collection.query(
                    query_texts=[query], n_results=2
                )
                if results and results["documents"] and results["documents"][0]:
                    context_parts.append("\n**Related past conversations:**")
                    for doc in results["documents"][0]:
                        context_parts.append(f"- {doc[:200]}...")
            except Exception:
                pass

        # Get user preferences
        user_name = await self.get_user_preference("user_name")
        if user_name:
            context_parts.insert(0, f"**User's name:** {user_name}")

        if context_parts:
            return "\n".join(context_parts)
        return ""

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._db_engine:
            await self._db_engine.dispose()
        logger.info("Memory service shut down")
