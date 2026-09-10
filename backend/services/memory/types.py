"""
JARVIS AI OS — Unified Memory Type Definitions & Schemas.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time


class MemoryType(str, Enum):
    WORKING = "working"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryItem(BaseModel):
    id: str
    content: str
    memory_type: MemoryType = MemoryType.LONG_TERM
    importance: MemoryImportance = MemoryImportance.MEDIUM
    metadata: Dict[str, Any] = Field(default_factory=dict)
    distance: Optional[float] = None
    timestamp: float = Field(default_factory=time.time)


class EpisodeRecord(BaseModel):
    id: str
    goal: str
    plan: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    execution_steps: List[Dict[str, Any]] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
    result: str = ""
    success: bool = True
    confidence_score: float = 1.0
    failure_reason: Optional[str] = None
    recovery_method: Optional[str] = None
    alternative_method: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class StrategyScore(BaseModel):
    strategy: str
    name: str
    confidence: float
    success_count: int = 0
    fail_count: int = 0
    category: str = "ui_automation"


class SearchResult(BaseModel):
    id: str
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
