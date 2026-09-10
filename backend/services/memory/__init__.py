"""
JARVIS AI OS — Unified Memory Subsystem Package.

Exports:
- MemoryManager: Central unified orchestrator
- MemoryService: Backward-compatible alias for MemoryManager
- WorkingMemory: Sliding-window turn buffer, active session, language tracking
- LongTermMemory: Persistent user facts, preferences, knowledge graph
- EpisodicMemory: Task execution traces, strategy confidence, workflows, lessons
- SemanticMemory: Document knowledge base & RAG
- Types: MemoryItem, EpisodeRecord, MemoryType, StrategyScore, SearchResult
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
