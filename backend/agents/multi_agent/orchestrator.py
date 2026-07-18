import asyncio
from typing import Dict, Any, List
from loguru import logger
from backend.utils.event_bus import EventBus

class AgentMessage:
    def __init__(self, sender: str, recipient: str, content: str, payload: Any = None):
        self.sender = sender
        self.recipient = recipient
        self.content = content
        self.payload = payload

class HierarchicalOrchestrator:
    """Coordinates collaborative execution across CEO, Planner, and Worker Agent layers."""
    
    def __init__(self, event_bus: EventBus, service_manager: Any):
        self.event_bus = event_bus
        self.service_manager = service_manager
        self.agent_message_history: List[AgentMessage] = []
        
    async def send_agent_message(self, sender: str, recipient: str, content: str, payload: Any = None) -> None:
        """Route message from one agent to another and log to event bus."""
        msg = AgentMessage(sender, recipient, content, payload)
        self.agent_message_history.append(msg)
        
        logger.info(f"[Agent Communication] {sender} ➔ {recipient}: '{content}'")
        await self.event_bus.publish("agent.message", {
            "sender": sender,
            "recipient": recipient,
            "content": content,
            "payload": payload
        })

    async def execute_goal(self, user_goal: str) -> str:
        """Run the multi-agent orchestration loop to complete a high-level goal."""
        logger.info(f"CEO Agent received user goal: '{user_goal}'")
        
        # 1. CEO requests plan from Planner
        await self.send_agent_message("CEO", "Planner", f"Decompose goal: {user_goal}")
        plan_steps = await self._run_planner_agent(user_goal)
        await self.send_agent_message("Planner", "CEO", f"Generated {len(plan_steps)} steps", plan_steps)
        
        # 2. CEO executes each step by delegating to specialized worker agents
        results = []
        for i, step in enumerate(plan_steps):
            worker_name = self._resolve_worker_for_step(step)
            await self.send_agent_message("CEO", worker_name, f"Execute step {i+1}: {step}")
            
            # Execute step using the selected worker
            res = await self._run_worker_agent(worker_name, step)
            results.append(res)
            
            await self.send_agent_message(worker_name, "CEO", f"Completed step {i+1}", res)
            
        # 3. CEO summarizes results for the user
        summary_prompt = f"Summarize execution results: {results} for goal: {user_goal}"
        final_answer = f"Completed goal '{user_goal}'. Execution results summary: {results}"
        logger.info("CEO Agent finalized goal execution.")
        return final_answer

    async def _run_planner_agent(self, goal: str) -> List[str]:
        """Simple mockup of a Planner agent generating sequential tasks."""
        await asyncio.sleep(0.1)
        # In a real run, this would query LLM. Here, we build a structured plan.
        goal_lower = goal.lower()
        if "code" in goal_lower or "script" in goal_lower:
            return ["Write python code script", "Execute script in sandbox"]
        if "file" in goal_lower or "read" in goal_lower or "write" in goal_lower:
            return ["Search directory for matching files", "Read file contents", "Validate content structure"]
        return ["Analyze context requirements", "Fetch system state metrics"]
        
    def _resolve_worker_for_step(self, step: str) -> str:
        step_lower = step.lower()
        if "file" in step_lower or "directory" in step_lower or "read" in step_lower or "write" in step_lower:
            return "FileWorker"
        if "code" in step_lower or "script" in step_lower:
            return "CodingWorker"
        if "system" in step_lower or "shell" in step_lower:
            return "DesktopWorker"
        return "ResearchWorker"
        
    async def _run_worker_agent(self, worker_name: str, step: str) -> Dict[str, Any]:
        """Mock execution of worker tasks using local tools and services."""
        await asyncio.sleep(0.1)
        logger.debug(f"Running {worker_name} executor on step: '{step}'")
        
        # Access safety and sandbox from service manager if needed
        try:
            sandbox = await self.service_manager.get("security_sandbox")
            # Example mock execution: if it requires code sandbox runs
            if worker_name == "CodingWorker":
                res = await sandbox.execute_python("print('Dynamic sandbox verification execution')")
                return {"status": "success", "worker": worker_name, "output": res.stdout}
        except Exception:
            pass
            
        return {"status": "success", "worker": worker_name, "details": f"Executed: {step}"}
