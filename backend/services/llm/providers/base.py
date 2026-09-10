"""Base LLM Provider Interface."""
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

class BaseLLMProvider(ABC):
    @abstractmethod
    async def process_message(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        pass
