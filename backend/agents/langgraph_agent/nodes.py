from typing import Dict, Any, List, Optional
from loguru import logger
import json

from langchain_core.runnables import RunnableConfig
from backend.agents.langgraph_agent.state import AgentState
from backend.agents.langgraph_agent.tools import get_tools


def format_history_for_prash(messages: List[Any]) -> List[Dict[str, str]]:
    """Convert state messages or history into list of dicts required by PrashEngine."""
    formatted = []
    if not messages:
        return formatted
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            if role in ("user", "assistant"):
                formatted.append({
                    "role": role,
                    "content": msg.get("content", "")
                })
        elif hasattr(msg, "type"):  # LangChain BaseMessage
            role = None
            if msg.type == "human":
                role = "user"
            elif msg.type == "ai":
                role = "assistant"
            if role:
                formatted.append({
                    "role": role,
                    "content": getattr(msg, "content", "")
                })
    return formatted


def parse_json_plan(text: str) -> List[str]:
    """Parse JSON plan list of strings with robust fallback parsing."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [str(item) for item in data]
    except Exception as e:
        logger.warning(f"JSON parsing failed for plan, falling back to line splitting: {e}")
        
    # Fallback to line splitting
    steps = []
    for line in cleaned.split("\n"):
        line = line.strip()
        if not line:
            continue
        line = line.lstrip("-* \t")
        if line.startswith(tuple(f"{i}." for i in range(1, 20))):
            line = line.split(".", 1)[1].strip()
        if line:
            steps.append(line)
    return steps


def parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON tool call response into structured dict."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "name" in data:
            return {
                "name": data["name"],
                "args": data.get("args", {})
            }
    except Exception as e:
        logger.warning(f"Failed to parse tool call JSON: {e}")
    return None


async def prash_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """Queries PrashEngine, computes confidence, and routes to tool planning or direct response."""
    logger.info("Entering prash_node...")
    
    # Initialize defaults to prevent KeyErrors
    state.setdefault("query", "")
    state.setdefault("messages", [])
    state.setdefault("plan", [])
    state.setdefault("current_step_index", 0)
    state.setdefault("tool_calls", [])
    state.setdefault("tool_results", [])
    state.setdefault("logs", [])
    state.setdefault("status", "running")
    state.setdefault("pending_confirmation", None)
    state.setdefault("prash_confident", False)
    state.setdefault("prash_response", "")
    state.setdefault("user_response", None)
    state.setdefault("final_output", "")

    # Skip querying PrashEngine if we are resuming from a user response/confirmation
    if state.get("user_response") is not None or state.get("pending_confirmation") is not None:
        logger.info("Resuming execution path. Skipping PrashEngine query.")
        return state

    prash_engine = config.get("configurable", {}).get("prash_engine")
    if not prash_engine:
        logger.error("PrashEngine not found in config configurable.")
        state["status"] = "fallback"
        state["prash_confident"] = False
        state["logs"].append("PrashEngine not available in config configurable.")
        return state

    # Ensure Prash is fully loaded before querying
    if not getattr(prash_engine, "_loaded", False):
        logger.info("Lazy-initializing PrashEngine in prash_node...")
        await prash_engine.init()

    query = state.get("query", "")
    history = state.get("messages", [])
    history_from_config = config.get("configurable", {}).get("history", [])
    if history_from_config and not history:
        history = history_from_config

    formatted_history = format_history_for_prash(history)
    state["logs"].append(f"Querying PrashEngine with query: '{query}'")
    
    try:
        response_text, is_confident, metadata = await prash_engine.generate(
            prompt=query,
            conversation_history=formatted_history
        )
        
        prash_confident = is_confident and len(response_text.strip()) > 5
        state["prash_confident"] = prash_confident
        state["logs"].append(f"PrashEngine confidence: {prash_confident} (entropy: {metadata.get('entropy', 'N/A')})")
        
        if not prash_confident:
            state["status"] = "fallback"
            state["logs"].append("Prash is not confident. Routing to fallback.")
            return state
            
        state["prash_response"] = response_text
        
        # Check if tool is required
        keywords = [
            "opening", "typing", "pressing", "playing", "querying", 
            "taking", "running", "minimizing", "searching", "storing", 
            "retrieving", "installing"
        ]
        response_lower = response_text.lower()
        tool_required = any(keyword in response_lower for keyword in keywords)
        
        if tool_required:
            state["status"] = "running"
            state["logs"].append("Action-oriented terms detected in response. Tool execution required.")
        else:
            state["status"] = "completed"
            state["final_output"] = response_text
            state["logs"].append("No tools required. Returning Prash direct response.")
            
    except Exception as e:
        logger.exception("Error in prash_node: {}", e)
        state["status"] = "fallback"
        state["prash_confident"] = False
        state["logs"].append(f"Error querying Prash: {str(e)}")
        
    return state


async def planner_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """Uses fallback LLM service simple_completion to generate execution steps."""
    logger.info("Entering planner_node...")
    llm_service = config.get("configurable", {}).get("llm_service")
    if not llm_service:
        logger.error("LLMService not found in config configurable.")
        state["status"] = "fallback"
        state["logs"].append("LLMService not available for planning.")
        return state

    query = state.get("query", "")
    prash_response = state.get("prash_response", "")
    state["logs"].append("Creating execution plan...")
    
    system_prompt = (
        "You are JARVIS's execution planner. Given a user query and the expected response, "
        "generate a sequential plan of execution steps (commands or tool uses) needed to fulfill the request. "
        "Output ONLY a raw JSON array of strings representing the steps. Do not include markdown formatting, backticks, or any explanation.\n"
        "Example output:\n"
        '["create folder test", "run terminal command pip install pandas", "web search weather in Paris"]'
    )
    prompt = f"User Query: {query}\nExpected Response: {prash_response}"
    
    try:
        plan_text = await llm_service.simple_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1
        )
        plan = parse_json_plan(plan_text)
        state["plan"] = plan
        state["current_step_index"] = 0
        state["logs"].append(f"Generated execution plan: {json.dumps(plan)}")
    except Exception as e:
        logger.exception("Error in planner_node: {}", e)
        state["status"] = "failed"
        state["logs"].append(f"Failed to generate plan: {str(e)}")
        
    return state


async def tool_selection_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """Resolves the current step into a structured tool call using fallback LLM service."""
    logger.info("Entering tool_selection_node...")
    if state.get("status") == "failed":
        logger.warning("Agent status is failed. Skipping tool selection.")
        return state
    llm_service = config.get("configurable", {}).get("llm_service")
    browser_service = config.get("configurable", {}).get("browser_service")
    if not llm_service:
        logger.error("LLMService not found in config configurable.")
        state["status"] = "failed"
        state["logs"].append("LLMService not available for tool selection.")
        return state

    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)
    
    if current_index >= len(plan):
        state["logs"].append("All plan steps completed.")
        state["tool_calls"] = []
        return state

    current_step = plan[current_index]
    state["logs"].append(f"Resolving step {current_index + 1}/{len(plan)}: '{current_step}'")
    
    tools = get_tools(browser_service=browser_service)
    tools_desc = []
    for t in tools:
        tools_desc.append({
            "name": t.name,
            "description": t.description,
            "args_schema": getattr(t, "args", {})
        })
        
    system_prompt = (
        "You are JARVIS's tool selector. Given the user's overall query, the current step in the execution plan, "
        "previous tool results, and a list of available tools, choose the single best tool to execute the current step "
        "and construct its exact arguments.\n\n"
        "Available Tools:\n"
        f"{json.dumps(tools_desc, indent=2)}\n\n"
        "Output ONLY a raw JSON object with the keys 'name' and 'args'. Do not include markdown code block formatting or backticks.\n"
        "Example Output:\n"
        '{"name": "file_system_tool", "args": {"action": "create_file", "path": "C:\\\\test\\\\file.txt", "content": "hello"}}\n'
    )
    
    history_str = json.dumps(state.get("tool_results", []), indent=2)
    prompt = (
        f"User Query: {state.get('query', '')}\n"
        f"Execution Plan: {json.dumps(plan)}\n"
        f"Current Step Index: {current_index}\n"
        f"Step to Execute: {current_step}\n"
        f"Previous Tool Results:\n{history_str}"
    )
    
    try:
        tool_call_text = await llm_service.simple_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1
        )
        tool_call = parse_tool_call(tool_call_text)
        if tool_call:
            state["tool_calls"] = [tool_call]
            state["logs"].append(f"Selected tool: '{tool_call['name']}' with args: {json.dumps(tool_call['args'])}")
        else:
            state["logs"].append(f"Failed to parse tool call from LLM response: {tool_call_text}")
            state["status"] = "failed"
    except Exception as e:
        logger.exception("Error in tool_selection_node: {}", e)
        state["status"] = "failed"
        state["logs"].append(f"Failed to select tool: {str(e)}")
        
    return state


async def tool_execution_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """Executes the selected tool, handling interrupts for safety confirmations and user inputs."""
    logger.info("Entering tool_execution_node...")
    browser_service = config.get("configurable", {}).get("browser_service")
    
    tools = get_tools(browser_service=browser_service)
    tool_map = {t.name: t for t in tools}
    
    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        state["logs"].append("No tool selected for execution.")
        state["status"] = "failed"
        return state
        
    tool_call = tool_calls[0]
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    
    user_response = state.get("user_response")
    pending_conf = state.get("pending_confirmation")
    tool_output = None
    
    # Check if we are resuming from a paused state
    if user_response is not None:
        state["logs"].append(f"Resuming execution with user response: '{user_response}'")
        
        # 1. Was it a user input tool?
        if tool_name == "user_input_tool" or (pending_conf and "__USER_INPUT_REQUIRED__" in pending_conf):
            tool_output = user_response
            state["logs"].append(f"User input received: {tool_output}")
            
        # 2. Was it a safety confirmation?
        elif pending_conf and "__CONFIRMATION_REQUIRED__" in pending_conf:
            resp_lower = user_response.strip().lower()
            confirmed = resp_lower in ["yes", "y", "confirm", "ok", "proceed", "approve", "go ahead"]
            
            if confirmed:
                state["logs"].append("User confirmed destructive command. Executing command bypassing warning.")
                if tool_name == "cmd_tool":
                    tool_args = dict(tool_args)
                    tool_args["bypass_safety"] = True
            else:
                tool_output = f"Action blocked: user denied permission to execute '{tool_name}'."
                state["logs"].append(f"Action denied: {tool_output}")
                
        # Clear fields since we have consumed the response
        state["user_response"] = None
        state["pending_confirmation"] = None
        
    # Run the tool if output hasn't been set by permission denial or user input resume
    if tool_output is None:
        if tool_name not in tool_map:
            error_msg = f"Error: Tool '{tool_name}' is not registered."
            logger.error(error_msg)
            tool_output = error_msg
        else:
            state["logs"].append(f"Executing tool '{tool_name}'...")
            try:
                t = tool_map[tool_name]
                tool_output = await t.ainvoke(tool_args)
            except Exception as e:
                logger.exception("Error executing tool {}: {}", tool_name, e)
                tool_output = f"Error executing tool '{tool_name}': {str(e)}"
                
    # Check if tool asks for permission or input
    if isinstance(tool_output, str) and tool_output.startswith("__CONFIRMATION_REQUIRED__:"):
        state["status"] = "waiting_for_user"
        state["pending_confirmation"] = tool_output
        state["logs"].append(f"Safety confirmation required: {tool_output}")
        return state
        
    if isinstance(tool_output, str) and tool_output.startswith("__USER_INPUT_REQUIRED__:"):
        state["status"] = "waiting_for_user"
        state["pending_confirmation"] = tool_output
        state["logs"].append(f"User input required: {tool_output}")
        return state

    # Step successful
    result_entry = {
        "step_index": state["current_step_index"],
        "step": state["plan"][state["current_step_index"]] if state["current_step_index"] < len(state["plan"]) else "unknown",
        "tool": tool_name,
        "arguments": tool_args,
        "result": tool_output
    }
    state["tool_results"].append(result_entry)
    state["logs"].append(f"Tool '{tool_name}' executed. Result: {str(tool_output)[:300]}...")
    
    # Increment step index and clean current tool call
    state["current_step_index"] += 1
    state["tool_calls"] = []
    state["status"] = "running"
    
    return state


async def result_validation_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """Validates executed tool outputs, triggering LLM decision to retry, replan, or proceed on errors."""
    logger.info("Entering result_validation_node...")
    llm_service = config.get("configurable", {}).get("llm_service")
    if not llm_service:
        logger.error("LLMService not found in config configurable.")
        return state

    results = state.get("tool_results", [])
    if not results:
        return state

    last_result = results[-1]
    result_str = str(last_result.get("result", ""))
    
    # Detect failures/errors in terminal/python tools
    is_failed = "error" in result_str.lower() or "failed" in result_str.lower()
    
    if "EXIT CODE:" in result_str:
        try:
            exit_code = int(result_str.split("EXIT CODE:")[1].strip())
            if exit_code != 0:
                is_failed = True
        except Exception:
            pass
            
    if "exit_code" in result_str:
        try:
            data = json.loads(result_str)
            if data.get("exit_code", 0) != 0:
                is_failed = True
        except Exception:
            pass

    if is_failed:
        state["logs"].append(f"Potential execution failure detected for step: '{last_result.get('step')}'")
        
        system_prompt = (
            "You are JARVIS's validation system. A step in the execution plan has failed or returned an error.\n"
            "Analyze the failure and decide the next course of action. Output exactly one of the following decisions:\n"
            "1. 'retry': Retry the failed step.\n"
            "2. 'replan': Re-plan the remaining steps. You must output the new plan in a JSON array format starting with '[' and ending with ']'.\n"
            "3. 'proceed': Ignore the failure and proceed with the next step.\n\n"
            "Output format:\n"
            "If your decision is retry, output exactly: retry\n"
            "If your decision is proceed, output exactly: proceed\n"
            "If your decision is replan, output the decision followed by the new plan JSON, e.g.:\n"
            "replan: [\"new step 1\", \"new step 2\"]\n"
        )
        
        prompt = (
            f"User Query: {state.get('query')}\n"
            f"Execution Plan: {json.dumps(state.get('plan'))}\n"
            f"Failed Step Index: {last_result.get('step_index')}\n"
            f"Failed Step: {last_result.get('step')}\n"
            f"Result: {result_str[:1000]}"
        )
        
        try:
            decision_text = await llm_service.simple_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )
            decision_text = decision_text.strip()
            state["logs"].append(f"Validation decision: {decision_text}")
            
            if decision_text.lower() == "retry":
                state["current_step_index"] = max(0, state["current_step_index"] - 1)
                state["tool_results"].pop()
                state["logs"].append("Retrying failed step...")
                
            elif decision_text.lower().startswith("replan"):
                parts = decision_text.split(":", 1)
                new_plan_json = parts[1] if len(parts) > 1 else decision_text
                new_plan = parse_json_plan(new_plan_json)
                if new_plan:
                    state["plan"] = state["plan"][:state["current_step_index"]] + new_plan
                    state["logs"].append(f"Re-planned remaining steps: {json.dumps(state['plan'])}")
                else:
                    state["logs"].append("Failed to parse new plan. Proceeding with original plan.")
            else:
                state["logs"].append("Validation decided to proceed despite failure.")
        except Exception as e:
            logger.exception("Error in result_validation_node: {}", e)
            state["logs"].append(f"Validation error: {str(e)}. Proceeding anyway.")
            
    return state


async def prash_generator_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """Takes all tool execution results and query, and generates the final response via PrashEngine."""
    logger.info("Entering prash_generator_node...")
    prash_engine = config.get("configurable", {}).get("prash_engine")
    llm_service = config.get("configurable", {}).get("llm_service")
    if not prash_engine:
        logger.error("PrashEngine not found in config configurable.")
        state["status"] = "failed"
        return state

    query = state.get("query", "")
    results = state.get("tool_results", [])
    
    results_summary = ""
    for r in results:
        results_summary += (
            f"Step: {r.get('step')}\n"
            f"Tool Executed: {r.get('tool')}\n"
            f"Arguments: {json.dumps(r.get('arguments'))}\n"
            f"Result: {r.get('result')}\n"
            f"{'-'*40}\n"
        )
        
    generator_prompt = (
        f"You are JARVIS, a helpful AI desktop assistant. The user asked: '{query}'\n"
        f"The following actions were taken to fulfill this request:\n\n{results_summary}\n"
        f"Please provide a final, polite, and comprehensive conversational response to the user summarizing "
        f"the actions taken and presenting any relevant outputs cleanly."
    )
    
    state["logs"].append("Generating final response via PrashEngine...")
    try:
        response_text, is_confident, metadata = await prash_engine.generate(
            prompt=generator_prompt,
            conversation_history=[]
        )
        if is_confident and response_text.strip():
            state["final_output"] = response_text
            state["status"] = "completed"
            state["logs"].append("Final response generated successfully via Prash.")
        else:
            state["logs"].append("Prash final response not confident. Falling back to LLM service for summary...")
            if llm_service:
                summary = await llm_service.simple_completion(
                    prompt=generator_prompt,
                    temperature=0.7
                )
                state["final_output"] = summary
                state["status"] = "completed"
                state["logs"].append("Final response generated successfully via fallback LLM.")
            else:
                state["final_output"] = "I completed the tasks successfully, sir."
                state["status"] = "completed"
    except Exception as e:
        logger.exception("Error in prash_generator_node: {}", e)
        state["status"] = "failed"
        state["logs"].append(f"Failed to generate final response: {str(e)}")
        
    return state


async def final_response_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """Sets final output and completes/closes the agent logs."""
    logger.info("Entering final_response_node...")
    if not state.get("final_output"):
        state["final_output"] = state.get("prash_response", "")
        
    state["status"] = "completed"
    state["logs"].append("Execution complete. Closing logs.")
    logger.info("LangGraph execution completed successfully.")
    return state
