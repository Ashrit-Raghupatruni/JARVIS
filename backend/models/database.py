"""
JARVIS AI Desktop Assistant - Database Models.

Async SQLAlchemy ORM models for persistent storage of conversations,
messages, user preferences, command logs, and task logs. Uses aiosqlite
for non-blocking database operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    func,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from backend.utils.logger import logger


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Base
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all JARVIS ORM models."""

    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class Conversation(Base):
    """
    A conversation session between the user and JARVIS.

    Groups related messages together with a title and timestamps.
    """

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, default="Untitled Conversation")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.timestamp",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title='{self.title}')>"


class Message(Base):
    """
    A single message within a conversation.

    Stores the role (user, assistant, system, tool) and text content
    along with a precise timestamp.
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # user | assistant | system | tool
    content = Column(Text, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        preview = self.content[:50] if self.content else ""
        return f"<Message(id={self.id}, role='{self.role}', content='{preview}...')>"


class UserPreference(Base):
    """
    Key-value store for user preferences and settings.

    Allows JARVIS to remember user preferences across sessions
    (e.g., preferred browser, nickname, timezone).
    """

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<UserPreference(key='{self.key}', value='{self.value[:30]}')>"


class CommandLog(Base):
    """
    Log of commands executed by JARVIS.

    Tracks what was run, the result, and whether it succeeded,
    for audit and debugging purposes.
    """

    __tablename__ = "command_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="success")  # success | error | blocked
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<CommandLog(id={self.id}, status='{self.status}')>"


class TaskLog(Base):
    """
    Log of multi-step tasks planned and executed by the agent.

    Stores the task description, serialised step data (JSON),
    and timing information.
    """

    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_description = Column(Text, nullable=False)
    steps_json = Column(Text, nullable=True)  # JSON-serialised list of AgentStep dicts
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TaskLog(id={self.id}, status='{self.status}')>"


class ProviderMetric(Base):
    """Logs LLM provider performance statistics from benchmarks."""

    __tablename__ = "provider_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    latency = Column(Float, nullable=False)
    throughput = Column(Float, nullable=True)
    cost = Column(Float, nullable=False, default=0.0)
    success = Column(Integer, nullable=False)  # 1 = success, 0 = fail
    error_message = Column(Text, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


class RoutingDecision(Base):
    """Logs all user requests, which provider was selected, and performance details."""

    __tablename__ = "routing_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    selected_provider = Column(String(50), nullable=False)
    selected_model = Column(String(100), nullable=False)
    latency = Column(Float, nullable=False)
    success = Column(Integer, nullable=False)
    fallback_count = Column(Integer, nullable=False, default=0)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=False, default=0.0)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


class MemoryLog(Base):
    """Local cache of semantic knowledge and facts with importance levels."""

    __tablename__ = "memory_logs"

    id = Column(String(50), primary_key=True)  # ChromaDB ID matching
    content = Column(Text, nullable=False)
    importance = Column(String(20), nullable=False, default="medium")  # low | medium | high | critical
    is_consolidated = Column(Integer, nullable=False, default=0)  # 0 = false, 1 = true
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


class LessonLearned(Base):
    """Mistakes made by the agent and user corrections for dynamic prompt injection."""

    __tablename__ = "lessons_learned"

    id = Column(String(50), primary_key=True)  # lesson_...
    trigger_keywords = Column(Text, nullable=False)  # Comma-separated keywords
    error_description = Column(Text, nullable=False)
    correction = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


class SuccessfulWorkflow(Base):
    """Execution plans and workflows that previously completed successfully."""

    __tablename__ = "successful_workflows"

    id = Column(String(50), primary_key=True)  # workflow_...
    task_description = Column(Text, nullable=False)
    steps_json = Column(Text, nullable=False)  # Serialized steps list
    optimized_prompt = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Engine & Session Factory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker] = None


def get_engine(database_url: str):
    """
    Create or retrieve the async SQLAlchemy engine.

    Args:
        database_url: Async SQLite connection string,
                      e.g. ``sqlite+aiosqlite:///path/to/jarvis.db``.

    Returns:
        The async engine instance.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )
        logger.info("Database engine created: {}", database_url)
    return _engine


def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """
    Create or retrieve the async session factory.

    Args:
        database_url: Async SQLite connection string.

    Returns:
        An ``async_sessionmaker`` bound to the engine.
    """
    global _session_factory
    if _session_factory is None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Session factory created")
    return _session_factory


async def init_db(database_url: str) -> None:
    """
    Initialise the database — create all tables if they do not exist.

    Should be called once during application startup.

    Args:
        database_url: Async SQLite connection string.
    """
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised successfully")


async def close_db() -> None:
    """
    Dispose of the database engine and release connections.

    Should be called during application shutdown.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")
