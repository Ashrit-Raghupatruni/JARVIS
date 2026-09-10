"""
Tool parsing, filtering, and text execution utilities for LLM Service.
"""
import json
import re
import time
from typing import Any, Dict, List, Optional
from backend.utils.logger import logger
from backend.services.llm.prompts import TOOL_DEFINITIONS

def try_parse_json_tool_call(text: str) -> Optional[dict]:
    """Check if the text is a JSON tool call and parse it."""
    text_stripped = text.strip()
    # Strip markdown code block wrappers
    if text_stripped.startswith("```"):
        lines = text_stripped.split("\n")
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1] == "```":
            text_stripped = "\n".join(lines[1:-1]).strip()
            
    if text_stripped.startswith("{") and text_stripped.endswith("}"):
        try:
            import json
            data = json.loads(text_stripped)
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                return data
        except Exception:
            pass
    return None


def try_parse_xml_tool_call(text: str) -> Optional[dict]:
    """Check if the text contains an XML-style function call like <function=name>args</function>."""
    import re
    import json
    # Match <function=name>arguments</function>
    match = re.search(r'<function=(\w+)>(.*?)</function>', text, re.DOTALL)
    if match:
        name = match.group(1)
        args_text = match.group(2).strip()
        try:
            args = json.loads(args_text)
        except Exception:
            args = {}
        return {"name": name, "arguments": args, "raw": match.group(0)}
    return None


def clean_function_calls_from_text(text: str) -> str:
    """Remove XML-style function tags, JSON blocks, and internal tool leakages from text to keep it clean for display."""
    if not text:
        return ""
    import re
    import json
    
    # 1. Remove XML tags: <function=name>...</function>
    text = re.sub(r'<function=\w+>.*?</function>', '', text, flags=re.DOTALL)
    
    # 2. Remove <result>...</result> if present
    text = re.sub(r'<result>.*?</result>', '', text, flags=re.DOTALL)
    
    # 3. Remove raw JSON markdown blocks that look like tool calls
    code_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL)
    for block in code_blocks:
        try:
            parsed = json.loads(block.strip())
            tool_keys = {"name", "arguments", "function", "call", "query", "tool_call_id"}
            if any(k in parsed for k in tool_keys):
                # Replace variations with and without newlines
                for prefix in ["```json", "```"]:
                    text = text.replace(f"{prefix}\n{block}\n```", "")
                    text = text.replace(f"{prefix}{block}```", "")
        except Exception:
            pass
            
    # 4. Remove inline JSON blocks that look like tool calls or results
    inline_blocks = re.findall(r'(\{.*?\})', text, flags=re.DOTALL)
    for block in inline_blocks:
        try:
            parsed = json.loads(block.strip())
            tool_keys = {"name", "arguments", "function", "call", "query", "tool_call_id"}
            if any(k in parsed for k in tool_keys):
                text = text.replace(block, "")
        except Exception:
            pass

    # Remove leftover brackets/curlies artifacts
    text = re.sub(r'\{\s*\}', '', text)

    # 5. Remove JSON blocks if the entire response is a JSON block
    text_stripped = text.strip()
    if text_stripped.startswith("{") and text_stripped.endswith("}"):
        try:
            json.loads(text_stripped)
            return ""
        except Exception:
            pass
            
    return text.strip()



def filter_tools_for_query(query: str, skills_registry: Any = None) -> List[Dict[str, Any]]:
    raw_tools = []
    try:
        from backend.services.manager import ServiceManager
        tr = ServiceManager.get_instance("tool_registry")
        if not tr:
            from backend.services.tool_registry import ToolRegistry
            tr = ToolRegistry()
        raw_tools.extend(tr.get_tools_schema())
    except Exception as tr_err:
        logger.debug("ToolRegistry schema load notice: {}", tr_err)

    if skills_registry:
        try:
            raw_tools.extend(skills_registry.get_all_tool_definitions())
        except Exception as sk_err:
            logger.debug("SkillsRegistry schema load notice: {}", sk_err)
    
    raw_tools.extend(TOOL_DEFINITIONS)

    seen = set()
    merged = []
    for t in raw_tools:
        if isinstance(t, dict) and "function" in t and isinstance(t["function"], dict):
            name = t["function"].get("name")
            if name and name not in seen:
                seen.add(name)
                merged.append(t)

    if len(merged) > 20:
        core_priority = {
            "search_files", "read_file", "write_file", "create_file",
            "open_application", "click_element_by_name", "set_control_value", "type_text",
            "get_process_info", "list_running_processes", "web_search",
            "smart_file_search", "copy_file", "take_screenshot"
        }
        q_words = set(query.lower().split()) if query else set()

        def _score_tool(tool_item):
            fn = tool_item.get("function", {})
            t_name = fn.get("name", "").lower()
            t_desc = fn.get("description", "").lower()
            score = 0
            if t_name in core_priority:
                score += 15
            for w in q_words:
                if len(w) > 2:
                    if w in t_name:
                        score += 10
                    if w in t_desc:
                        score += 5
            return score

        merged.sort(key=_score_tool, reverse=True)
        merged = merged[:20]

    return merged


async def check_and_execute_text_tool_call(
    full_text: str,
    tool_executor: Any,
    messages: List[Dict[str, Any]],
    valid_tool_names: set,
) -> Optional[Dict[str, Any]]:
    parsed_call = try_parse_xml_tool_call(full_text) or try_parse_json_tool_call(full_text)
    if parsed_call:
        tool_name = parsed_call.get("name")
        tool_args = parsed_call.get("arguments", {})
        
        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except Exception:
                tool_args = {}
                
        if tool_name in valid_tool_names:
            logger.info("Interception: Detected plain-text tool call for '{}'", tool_name)
            tool_call_id = f"call_text_{int(time.time())}"
            
            messages.append({
                "role": "assistant",
                "content": full_text
            })
            
            if tool_executor:
                try:
                    result = await tool_executor(tool_name, tool_args)
                except Exception as e:
                    result = f"Error executing {tool_name}: {e}"
                    logger.error("Tool execution error: {}", e)
            else:
                result = f"Tool '{tool_name}' executed successfully (no executor connected)."
            
            is_xml = "<function=" in full_text
            if is_xml:
                messages.append({
                    "role": "user",
                    "content": f"<result>{result}</result>"
                })
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": str(result)
                })
            
            return {
                "tool_name": tool_name,
                "tool_args": tool_args,
                "result": str(result),
                "tool_call_id": tool_call_id
            }
    return None
