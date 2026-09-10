"""
Memory service for JARVIS.

Backwards-compatible module root re-exporting from backend.services.memory package.
Provides persistent memory using ChromaDB for semantic vector search,
SQLite for structured data storage, and unified MemoryManager.
"""

from backend.services.memory.manager import MemoryManager, MemoryService
from backend.services.memory.working_memory import WorkingMemory
from backend.services.memory.long_term_memory import LongTermMemory
from backend.services.memory.episodic_memory import EpisodicMemory
from backend.services.memory.semantic_memory import SemanticMemory
from backend.services.memory.types import (
    MemoryType,
    MemoryImportance,
    MemoryItem,
    EpisodeRecord,
    StrategyScore,
    SearchResult
)

__all__ = [
    "MemoryManager",
    "MemoryService",
    "WorkingMemory",
    "LongTermMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "MemoryType",
    "MemoryImportance",
    "MemoryItem",
    "EpisodeRecord",
    "StrategyScore",
    "SearchResult"
]
