"""
Base skill class and tool decorator for JARVIS skill plugin architecture.
"""

from typing import Any, Callable, Dict, List


def skill_tool(name: str, description: str, parameters: Dict[str, Any]):
    """Decorator to mark a skill method as a tool callable by the LLM."""
    def decorator(func: Callable[..., Any]):
        func._is_tool = True
        func._tool_info = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            }
        }
        return func
    return decorator


class BaseSkill:
    """Base class for all modular JARVIS skills."""

    @property
    def name(self) -> str:
        """Return the name of the skill."""
        return self.__class__.__name__

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Scans the class for decorated tools and returns their JSON definitions."""
        definitions = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, "_is_tool") and attr._is_tool:
                definitions.append(attr._tool_info)
        return definitions

    async def execute(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Executes a tool on this skill if it exists."""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, "_is_tool") and attr._is_tool:
                info = attr._tool_info
                if info["function"]["name"] == tool_name:
                    # Execute the async or sync method
                    import inspect
                    if inspect.iscoroutinefunction(attr):
                        return await attr(**args)
                    else:
                        return attr(**args)
        raise ValueError(f"Tool '{tool_name}' not found on skill '{self.name}'")
