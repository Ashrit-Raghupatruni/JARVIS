"""
Autonomous Agent Syndicate Skill for JARVIS.
Handles spawning, listing, and canceling background sub-agents.
"""

import uuid
from typing import Any, Dict, List, Optional

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger


class AgentSkill(BaseSkill):
    """Enables JARVIS to delegate long-running tasks to autonomous sub-agents executing headlessly."""

    def __init__(self, planner_agent=None) -> None:
        self.planner = planner_agent
        # Keep local map of spawned agents if app state is not bound yet
        self.local_agents: Dict[str, Any] = {}

    def _get_active_agents_dict(self) -> Dict[str, Any]:
        """Helper to retrieve dictionary of agents from FastAPI state or fall back to local map."""
        if self.planner and hasattr(self.planner, "llm") and hasattr(self.planner.llm, "skills_registry"):
            # Can check if app is bound
            try:
                from backend.main import app
                if not hasattr(app.state, "active_subagents"):
                    app.state.active_subagents = {}
                return app.state.active_subagents
            except Exception:
                pass
        return self.local_agents

    # ── Skill Tools ───────────────────────────────────────────────────────

    @skill_tool(
        name="spawn_subagent",
        description="Spawns a new autonomous sub-agent to execute a multi-step background task without blocking active conversation.",
        parameters={
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "Full task details and goals for the sub-agent (e.g. 'clean downloads and email duplicates log')"}
            },
            "required": ["task_description"]
        }
    )
    def spawn_subagent(self, task_description: str) -> str:
        if not self.planner:
            return "Planner agent reference not found; cannot spawn sub-agents."

        try:
            from backend.agents.subagent import SubAgentInstance
            from backend.main import app
            
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"
            
            # Create sub-agent using main app state reference
            agent = SubAgentInstance(
                agent_id=agent_id,
                task_description=task_description,
                planner_agent=self.planner,
                app_state=app.state
            )
            
            # Register in active registry
            active_dict = self._get_active_agents_dict()
            active_dict[agent_id] = agent
            
            # Start execution thread
            agent.start()
            
            return f"✓ Spawned autonomous sub-agent [{agent_id}] to execute task: '{task_description}'."
        except Exception as e:
            logger.error("Failed to spawn sub-agent: {}", e)
            return f"Failed to spawn sub-agent: {e}"

    @skill_tool(
        name="get_active_agents",
        description="Lists all currently running, completed, or cancelled autonomous background sub-agents and their progress.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def get_active_agents(self) -> str:
        active_dict = self._get_active_agents_dict()
        if not active_dict:
            return "No background sub-agents have been spawned in this session."

        lines = ["🤖 **Active Sub-Agent Syndicate** :"]
        for a_id, agent in active_dict.items():
            duration = int(time_duration(agent.started_at, agent.completed_at))
            lines.append(
                f"- **[{a_id}]** Context: '{agent.task_description[:50]}...'\n"
                f"  Status: **{agent.status.upper()}** | Progress: **{agent.progress * 100:.1f}%** | Runtime: {duration}s"
            )
            if agent.logs:
                lines.append(f"  Latest log: {agent.logs[-1]}")
                
        return "\n".join(lines)

    @skill_tool(
        name="abort_subagent",
        description="Cancels the execution of a running sub-agent by its ID.",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Unique ID of the agent to abort"}
            },
            "required": ["agent_id"]
        }
    )
    def abort_subagent(self, agent_id: str) -> str:
        active_dict = self._get_active_agents_dict()
        agent = active_dict.get(agent_id)
        if not agent:
            return f"No sub-agent found with ID '{agent_id}'."

        try:
            agent.abort()
            return f"✓ Aborted sub-agent [{agent_id}] successfully."
        except Exception as e:
            return f"Failed to abort sub-agent [{agent_id}]: {e}"


def time_duration(started: float, completed: Optional[float]) -> float:
    end = completed if completed else import_time()
    return max(0.0, end - started)


def import_time() -> float:
    import time
    return time.time()
