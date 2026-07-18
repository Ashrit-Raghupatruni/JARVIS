from abc import ABC, abstractmethod

class BaseService(ABC):
    """Base interface for all JARVIS modular services."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service (e.g. load models, open database connections)."""
        pass
        
    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully release any resources."""
        pass
