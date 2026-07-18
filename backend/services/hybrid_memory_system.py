import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

# Try to use NetworkX for Knowledge Graph tracking
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

class HybridMemorySystem:
    """Consolidates working, conversational, semantic, episodic, procedural, and graph memory structures."""
    
    def __init__(self, memory_dir: str = "data/memory"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.graph_path = self.memory_dir / "knowledge_graph.json"
        self.episodic_path = self.memory_dir / "episodic_memory.json"
        
        # 1. Working Memory (active context)
        self.working_memory: Dict[str, Any] = {}
        
        # 2. Conversation Memory
        self.conversation_memory: List[Dict[str, str]] = []
        
        # 3. Semantic Memory (key-value text correlations)
        self.semantic_memory: Dict[str, str] = {}
        
        # 4. Procedural Memory (workflow templates)
        self.procedural_memory: Dict[str, List[str]] = {
            "file_backup": ["Search directory", "Copy to archive", "Log backup status"],
            "system_audit": ["Fetch active processes", "Scan credential vault", "Write audit logs"]
        }
        
        # 5. Episodic Memory (past goal execution summaries)
        self.episodic_memory: List[Dict[str, Any]] = self._load_json(self.episodic_path, [])
        
        # 6. Knowledge Graph (relationship network)
        self._init_knowledge_graph()
        
    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading memory JSON file {path}: {e}")
        return default
        
    def _save_json(self, data: Any, path: Path) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory JSON file {path}: {e}")
            
    def _init_knowledge_graph(self) -> None:
        if HAS_NETWORKX:
            self.graph = nx.DiGraph()
            if self.graph_path.exists():
                try:
                    data = self._load_json(self.graph_path, {})
                    for node, attrs in data.get("nodes", {}).items():
                        self.graph.add_node(node, **attrs)
                    for edge in data.get("edges", []):
                        self.graph.add_edge(edge["source"], edge["target"], **edge.get("attrs", {}))
                    logger.info("✓ Knowledge graph memory loaded using NetworkX")
                except Exception as e:
                    logger.error(f"Failed to restore NetworkX graph from file: {e}")
        else:
            self.graph = {"nodes": {}, "edges": []}
            if self.graph_path.exists():
                self.graph = self._load_json(self.graph_path, {"nodes": {}, "edges": []})
                
    def save_knowledge_graph(self) -> None:
        """Serialize and save the knowledge graph state."""
        if HAS_NETWORKX:
            data = {
                "nodes": dict(self.graph.nodes(data=True)),
                "edges": [
                    {"source": u, "target": v, "attrs": d} 
                    for u, v, d in self.graph.edges(data=True)
                ]
            }
            self._save_json(data, self.graph_path)
        else:
            self._save_json(self.graph, self.graph_path)
        logger.info("✓ Knowledge graph saved to disk")
        
    def add_relationship(self, entity_a: str, relationship: str, entity_b: str) -> None:
        """Insert a relationship node/edge into the Knowledge Graph."""
        if HAS_NETWORKX:
            self.graph.add_node(entity_a, type="entity")
            self.graph.add_node(entity_b, type="entity")
            self.graph.add_edge(entity_a, entity_b, relationship=relationship)
        else:
            self.graph["nodes"][entity_a] = {"type": "entity"}
            self.graph["nodes"][entity_b] = {"type": "entity"}
            self.graph["edges"].append({
                "source": entity_a,
                "target": entity_b,
                "attrs": {"relationship": relationship}
            })
        self.save_knowledge_graph()
        
    def get_related_entities(self, entity: str) -> List[str]:
        """Fetch all related entities connected to a node."""
        if HAS_NETWORKX:
            if entity in self.graph:
                return list(self.graph.neighbors(entity))
        else:
            neighbors = []
            for edge in self.graph["edges"]:
                if edge["source"] == entity:
                    neighbors.append(edge["target"])
            return neighbors
        return []

    def record_episode(self, goal: str, result: str, success: bool = True) -> None:
        """Save a task execution trace in episodic memory."""
        episode = {
            "goal": goal,
            "result": result,
            "success": success,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self.episodic_memory.append(episode)
        self._save_json(self.episodic_memory, self.episodic_path)
        logger.info(f"Recorded episode for goal: '{goal}'")
