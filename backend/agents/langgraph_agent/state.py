from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    query: str
    messages: List[BaseMessage]
    plan: List[str]                  # List of steps (e.g. ["run cmd", "write script"])
    current_step_index: int          # Tracker for sequential execution
    tool_calls: List[Dict[str, Any]] # Tool calls list for current step: [{"name": "cmd", "args": {...}}]
    tool_results: List[Dict[str, Any]] # Executed tool results
    logs: List[str]                  # Log messages for UI streaming
    status: str                      # "running", "waiting_for_user", "completed", "failed", "fallback"
    pending_confirmation: Optional[str] # If paused, what command/action is waiting for user confirmation
    prash_confident: bool
    prash_response: str
    user_response: Optional[str]     # Input provided by user when resuming
    final_output: str
