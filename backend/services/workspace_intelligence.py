"""
JARVIS AI OS - Workspace Intelligence Engine.

Continuously analyzes current desktop context, active window titles, file paths,
and action history to infer:
- Current Project
- Current Goal
- Current Workflow (Coding, Research, Study, Debugging, Media, General)
- Recent Actions (Ring Buffer)
- Next Likely Action (Predictive Transition Model)
- Long-Term Habits (Persisted Transition Frequencies)
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from loguru import logger

from backend.config import PROJECT_ROOT


class WorkspaceContext(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    current_project: str = "JARVIS Personal AI OS"
    current_goal: str = "Desktop Automation & Observation"
    current_workflow: str = "General Desktop Activity"
    recent_actions: List[str] = Field(default_factory=list)
    next_likely_action: str = "Awaiting User Command"
    confidence: float = 0.85
    top_habits: List[Dict[str, Any]] = Field(default_factory=list)


class WorkspaceIntelligenceService:
    """Central engine for tracking session workflows, projects, and habit predictions."""

    def __init__(self, data_file: Optional[Path] = None) -> None:
        self.data_file = data_file or (PROJECT_ROOT / "data" / "user_habits.json")
        self._recent_actions: List[str] = []
        self._action_transitions: Dict[str, Dict[str, int]] = {}  # action_A -> { action_B: count }
        self._current_project: str = "JARVIS Core"
        self._current_goal: str = "Personal AI OS Development"
        self._current_workflow: str = "General Desktop Activity"
        self._load_habits()
        logger.info("WorkspaceIntelligenceService initialized (Habit Store: {})", self.data_file.name)

    def _load_habits(self) -> None:
        """Load persisted habit transition matrix from disk."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._action_transitions = raw.get("transitions", {})
                    logger.debug("Loaded {} habit transition rules", len(self._action_transitions))
            except Exception as e:
                logger.warning("Failed to load habit store: {}", e)

    def _save_habits(self) -> None:
        """Persist habit transition matrix to disk."""
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump({"transitions": self._action_transitions, "updated_at": time.time()}, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save habit store: {}", e)

    def record_action(self, action_name: str) -> None:
        """Record an executed desktop or tool action and update transition frequencies."""
        clean_act = action_name.lower().strip()
        if not clean_act:
            return

        if self._recent_actions:
            prev_act = self._recent_actions[-1]
            if prev_act != clean_act:
                if prev_act not in self._action_transitions:
                    self._action_transitions[prev_act] = {}
                self._action_transitions[prev_act][clean_act] = self._action_transitions[prev_act].get(clean_act, 0) + 1
                self._save_habits()

        self._recent_actions.append(clean_act)
        if len(self._recent_actions) > 20:
            self._recent_actions.pop(0)

    def set_goal(self, goal: str) -> None:
        """Update active operational goal."""
        self._current_goal = goal.strip()
        logger.info("Updated Workspace Goal: '{}'", self._current_goal)

    def update_from_desktop_state(self, active_app: str, window_title: str, browser_url: Optional[str] = None) -> WorkspaceContext:
        """Analyze active application, window title, and browser URL to infer project and workflow."""
        title_lower = window_title.lower()
        app_lower = active_app.lower()

        # Inquire Project Name
        if "jarvis" in title_lower or "jarvis" in app_lower:
            self._current_project = "JARVIS AI OS"
        elif "code" in app_lower or "vscode" in title_lower:
            if " - " in window_title:
                parts = window_title.split(" - ")
                self._current_project = parts[-2] if len(parts) >= 2 else parts[0]
            else:
                self._current_project = "Software Development Project"
        elif "chrome" in app_lower or "edge" in app_lower:
            if browser_url and "github.com" in browser_url:
                repo_parts = browser_url.replace("https://github.com/", "").split("/")
                if len(repo_parts) >= 2:
                    self._current_project = f"GitHub: {repo_parts[0]}/{repo_parts[1]}"
            else:
                self._current_project = "Web Research Session"

        # Inquire Workflow Classification
        if any(k in app_lower or k in title_lower for k in ["code", "vscode", "pycharm", "git", "terminal", "powershell"]):
            self._current_workflow = "Software Engineering & Coding"
        elif any(k in app_lower or k in title_lower for k in ["chrome", "edge", "firefox", "pdf", "acrobat", "research"]):
            self._current_workflow = "Web Research & Knowledge Indexing"
        elif any(k in app_lower or k in title_lower for k in ["notion", "notes", "word", "anki", "quiz"]):
            self._current_workflow = "Study & Learning Session"
        elif any(k in app_lower or k in title_lower for k in ["spotify", "vlc", "media", "youtube"]):
            self._current_workflow = "Media & Entertainment"
        else:
            self._current_workflow = "General Desktop Activity"

        # Predict Next Likely Action using habit transition matrix
        next_action = "Awaiting User Command"
        if self._recent_actions:
            last_act = self._recent_actions[-1]
            transitions = self._action_transitions.get(last_act, {})
            if transitions:
                next_action = max(transitions, key=transitions.get)

        # Top habits list
        top_habits_list = []
        for src, dests in list(self._action_transitions.items())[:5]:
            best_dest = max(dests, key=dests.get) if dests else "next_step"
            top_habits_list.append({"when": src, "then": best_dest, "frequency": dests.get(best_dest, 1)})

        return WorkspaceContext(
            timestamp=time.time(),
            current_project=self._current_project,
            current_goal=self._current_goal,
            current_workflow=self._current_workflow,
            recent_actions=self._recent_actions[-5:],
            next_likely_action=next_action,
            confidence=0.92,
            top_habits=top_habits_list
        )

    def get_context(self) -> WorkspaceContext:
        """Fetch current workspace context."""
        next_action = "Awaiting User Command"
        if self._recent_actions:
            last_act = self._recent_actions[-1]
            transitions = self._action_transitions.get(last_act, {})
            if transitions:
                next_action = max(transitions, key=transitions.get)

        top_habits_list = []
        for src, dests in list(self._action_transitions.items())[:5]:
            best_dest = max(dests, key=dests.get) if dests else "next_step"
            top_habits_list.append({"when": src, "then": best_dest, "frequency": dests.get(best_dest, 1)})

        return WorkspaceContext(
            timestamp=time.time(),
            current_project=self._current_project,
            current_goal=self._current_goal,
            current_workflow=self._current_workflow,
            recent_actions=self._recent_actions[-5:],
            next_likely_action=next_action,
            confidence=0.92,
            top_habits=top_habits_list
        )
