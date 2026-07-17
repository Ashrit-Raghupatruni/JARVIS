from typing import List, Dict, Any, Optional, AsyncGenerator
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agents.langgraph_agent.state import AgentState
from backend.agents.langgraph_agent.nodes import (
    prash_node,
    planner_node,
    tool_selection_node,
    tool_execution_node,
    result_validation_node,
    prash_generator_node,
    final_response_node
)


def route_after_prash(state: AgentState) -> str:
    """Routes state based on PrashEngine output and confidence."""
    # Check if we are resuming from a paused state (user confirmation/input path)
    if state.get("user_response") is not None or state.get("pending_confirmation") is not None:
        return "tool_execution"
        
    if not state.get("prash_confident", False):
        return "fallback"
        
    if state.get("status") == "completed":
        return "final_response"
        
    return "planner"


def route_after_execution(state: AgentState) -> str:
    """Routes state after executing a tool (pause if user input needed)."""
    if state.get("status") == "waiting_for_user":
        return "pause"
    if state.get("status") == "failed":
        return "fallback"
    return "result_validation"


def route_after_validation(state: AgentState) -> str:
    """Routes state after step result validation (loop back or finalize)."""
    if state.get("status") == "failed":
        return "fallback"
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)
    if current_index < len(plan):
        return "tool_selection"
    return "prash_generator"


# Create LangGraph StateMachine
workflow = StateGraph(AgentState)

# Register all nodes
workflow.add_node("prash", prash_node)
workflow.add_node("planner", planner_node)
workflow.add_node("tool_selection", tool_selection_node)
workflow.add_node("tool_execution", tool_execution_node)
workflow.add_node("result_validation", result_validation_node)
workflow.add_node("prash_generator", prash_generator_node)
workflow.add_node("final_response", final_response_node)

# Define transitions & edges
workflow.set_entry_point("prash")

workflow.add_conditional_edges(
    "prash",
    route_after_prash,
    {
        "fallback": END,
        "final_response": "final_response",
        "planner": "planner",
        "tool_execution": "tool_execution"
    }
)

workflow.add_edge("planner", "tool_selection")
workflow.add_edge("tool_selection", "tool_execution")

workflow.add_conditional_edges(
    "tool_execution",
    route_after_execution,
    {
        "pause": END,
        "fallback": END,
        "result_validation": "result_validation"
    }
)

workflow.add_conditional_edges(
    "result_validation",
    route_after_validation,
    {
        "tool_selection": "tool_selection",
        "prash_generator": "prash_generator",
        "fallback": END
    }
)

workflow.add_edge("prash_generator", "final_response")
workflow.add_edge("final_response", END)


class PrashLangGraphAgent:
    """Constructs, compiles and runs the LangGraph StateMachine for Prash-based tool calling."""

    def __init__(self, llm_service: Any, browser_service: Any, prash_engine: Any) -> None:
        self.llm_service = llm_service
        self.browser_service = browser_service
        self.prash_engine = prash_engine
        
        # Compile with in-memory checkpointer
        self.checkpointer = MemorySaver()
        self.graph = workflow.compile(checkpointer=self.checkpointer)
        logger.info("LangGraph agent StateMachine compiled successfully.")

    async def run(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
        user_response: Optional[str] = None,
        state_checkpoint: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Executes the tool-calling graph or resumes execution from a checkpoint."""
        logger.info("Executing PrashLangGraphAgent...")
        
        thread_id = "default_session"
        config = {
            "configurable": {
                "thread_id": thread_id,
                "prash_engine": self.prash_engine,
                "llm_service": self.llm_service,
                "browser_service": self.browser_service,
                "history": history or []
            }
        }
        
        if state_checkpoint:
            logger.info("Resuming execution path from state checkpoint.")
            state_data = dict(state_checkpoint)
            
            # Merge the new user response
            if user_response is not None:
                state_data["user_response"] = user_response
                
            # Update graph state for the thread
            await self.graph.aupdate_state(config, state_data)
            
            # Resume graph execution (input=None)
            result = await self.graph.ainvoke(None, config)
        else:
            logger.info("Starting fresh execution run of the graph.")
            initial_state = {
                "query": query,
                "messages": history or [],
                "plan": [],
                "current_step_index": 0,
                "tool_calls": [],
                "tool_results": [],
                "logs": [],
                "status": "running",
                "pending_confirmation": None,
                "prash_confident": False,
                "prash_response": "",
                "user_response": user_response,
                "final_output": "",
            }
            
            result = await self.graph.ainvoke(initial_state, config)
            
        return dict(result)

    async def run_stream(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
        user_response: Optional[str] = None,
        state_checkpoint: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Runs the graph, yielding state dict updates step-by-step."""
        logger.info("Executing PrashLangGraphAgent in streaming mode...")
        
        thread_id = "default_session"
        config = {
            "configurable": {
                "thread_id": thread_id,
                "prash_engine": self.prash_engine,
                "llm_service": self.llm_service,
                "browser_service": self.browser_service,
                "history": history or []
            }
        }
        
        
        
        if state_checkpoint:
            logger.info("Resuming execution path from state checkpoint (streaming).")
            state_data = dict(state_checkpoint)
            if user_response is not None:
                state_data["user_response"] = user_response
                
            await self.graph.aupdate_state(config, state_data)
            
            async for chunk in self.graph.astream(None, config, stream_mode="updates"):
                current_state = await self.graph.aget_state(config)
                yield dict(current_state.values)
        else:
            logger.info("Starting fresh execution run of the graph (streaming).")
            initial_state = {
                "query": query,
                "messages": history or [],
                "plan": [],
                "current_step_index": 0,
                "tool_calls": [],
                "tool_results": [],
                "logs": [],
                "status": "running",
                "pending_confirmation": None,
                "prash_confident": False,
                "prash_response": "",
                "user_response": user_response,
                "final_output": "",
            }
            
            async for chunk in self.graph.astream(initial_state, config, stream_mode="updates"):
                current_state = await self.graph.aget_state(config)
                yield dict(current_state.values)
