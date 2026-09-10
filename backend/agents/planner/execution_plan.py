"""
Execution Plan step builder and WebSocket progress event formatter.
"""
from typing import List, Optional
from backend.models.schemas import AgentStep, AgentStepStatus, WSMessage


class ExecutionPlanTracker:
    def __init__(self, task_name: str = ""):
        self.task_name = task_name
        self.steps: List[AgentStep] = []

    def add_or_update_step(self, step: AgentStep) -> None:
        for idx, s in enumerate(self.steps):
            if s.id == step.id:
                self.steps[idx] = step
                return
        self.steps.append(step)

    def mark_completed(self, step_id: str, result: str = "") -> None:
        for s in self.steps:
            if s.id == step_id:
                s.status = AgentStepStatus.COMPLETED
                s.result = result
                break

    def mark_failed(self, step_id: str, error: str = "") -> None:
        for s in self.steps:
            if s.id == step_id:
                s.status = AgentStepStatus.FAILED
                s.result = error
                break

    def get_progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status in (AgentStepStatus.COMPLETED, AgentStepStatus.FAILED))
        return completed / len(self.steps)

    def to_progress_ws_message(self, task_description: Optional[str] = None) -> WSMessage:
        return WSMessage(
            type="agent_progress",
            data={
                "task": (task_description or self.task_name)[:100],
                "steps": [s.model_dump() for s in self.steps],
                "progress": self.get_progress(),
            },
        )
