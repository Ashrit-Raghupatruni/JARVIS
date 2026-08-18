"""
JARVIS AI OS — n8n Canvas <-> Workflow Translator & Graph Sync Engine.
======================================================================
Bi-directionally translates between JARVIS Visual Canvas JSON format and official n8n Workflow JSON format.
Preserves graph semantics: sequential steps, parallel branches, conditions (If true/false), loops, triggers, and parameters.
Generates proposed canvas graphs from natural-language user requests.
"""

import json
import time
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger


# Mapping between JARVIS Canvas node types and n8n node type definitions
CANVAS_TO_N8N_TYPE_MAP = {
    "trigger": "n8n-nodes-base.webhook",
    "manual_trigger": "n8n-nodes-base.manualTrigger",
    "action": "n8n-nodes-base.httpRequest",
    "script": "n8n-nodes-base.code",
    "condition": "n8n-nodes-base.if",
    "loop": "n8n-nodes-base.splitInBatches",
    "llm": "n8n-nodes-base.httpRequest"
}

N8N_TO_CANVAS_TYPE_MAP = {
    "n8n-nodes-base.webhook": "trigger",
    "n8n-nodes-base.manualTrigger": "trigger",
    "n8n-nodes-base.httpRequest": "action",
    "n8n-nodes-base.code": "script",
    "n8n-nodes-base.executeCommand": "script",
    "n8n-nodes-base.if": "condition",
    "n8n-nodes-base.splitInBatches": "loop"
}


class N8nWorkflowTranslator:
    """Translator between JARVIS Visual Canvas Graph and n8n Workflow Schema."""

    @staticmethod
    def canvas_to_n8n(canvas_graph: Dict[str, Any], workflow_name: str = "JARVIS Visual Workflow") -> Dict[str, Any]:
        """
        Convert JARVIS Visual Canvas graph JSON into a valid n8n Workflow definition.
        """
        canvas_nodes = canvas_graph.get("nodes", [])
        canvas_edges = canvas_graph.get("edges", [])

        # Build node id -> node object lookup & node id -> node name lookup
        id_to_node = {n["id"]: n for n in canvas_nodes}
        id_to_name = {n["id"]: n.get("title", n["id"]) for n in canvas_nodes}

        n8n_nodes = []
        for node in canvas_nodes:
            c_type = node.get("type", "action")
            n8n_type = CANVAS_TO_N8N_TYPE_MAP.get(c_type, "n8n-nodes-base.httpRequest")
            
            config = node.get("config", {})
            position = [int(node.get("x", 100)), int(node.get("y", 100))]
            
            n8n_node = {
                "id": node["id"],
                "name": id_to_name[node["id"]],
                "type": n8n_type,
                "typeVersion": 1,
                "position": position,
                "parameters": {
                    "description": node.get("desc", ""),
                    **config
                }
            }

            # Type specific parameters
            if c_type == "trigger":
                n8n_node["parameters"]["path"] = config.get("path", f"webhook-{node['id']}")
                n8n_node["parameters"]["httpMethod"] = config.get("method", "POST")
            elif c_type == "condition":
                n8n_node["parameters"]["conditions"] = config.get("conditions", {
                    "boolean": [{"value1": "={{ $json.pass }}", "value2": True}]
                })
            elif c_type == "llm":
                n8n_node["parameters"]["url"] = config.get("url", "http://localhost:8000/api/v1/command")
                n8n_node["parameters"]["method"] = "POST"
                n8n_node["parameters"]["bodyParametersUi"] = {
                    "parameter": [{"name": "text", "value": node.get("desc", "")}]
                }

            n8n_nodes.append(n8n_node)

        # Build connections dictionary
        # n8n format: connections[source_name]["main"][output_index] = [{"node": target_name, "type": "main", "index": 0}]
        connections: Dict[str, Dict[str, List[List[Dict[str, Any]]]]] = {}

        for edge in canvas_edges:
            src_id = edge.get("from")
            dst_id = edge.get("to")
            label = str(edge.get("label", "")).lower()

            if not src_id or not dst_id or src_id not in id_to_node or dst_id not in id_to_node:
                continue

            src_node = id_to_node[src_id]
            src_name = id_to_name[src_id]
            dst_name = id_to_name[dst_id]

            # Determine output branch index (0 for true/pass/default, 1 for false/fail)
            output_idx = 0
            if src_node.get("type") == "condition":
                if label in ["false", "fail", "no", "reject"]:
                    output_idx = 1
                else:
                    output_idx = 0

            if src_name not in connections:
                connections[src_name] = {"main": []}

            main_outputs = connections[src_name]["main"]

            # Ensure main_outputs list is long enough for output_idx
            while len(main_outputs) <= output_idx:
                main_outputs.append([])

            main_outputs[output_idx].append({
                "node": dst_name,
                "type": "main",
                "index": 0
            })

        n8n_workflow = {
            "name": workflow_name,
            "nodes": n8n_nodes,
            "connections": connections,
            "active": False,
            "settings": {
                "executionOrder": "v1"
            }
        }

        logger.info("Translated JARVIS Canvas graph ({} nodes, {} edges) -> n8n Workflow definition", len(n8n_nodes), len(canvas_edges))
        return n8n_workflow

    @staticmethod
    def n8n_to_canvas(n8n_workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert official n8n Workflow definition JSON into JARVIS Visual Canvas graph JSON.
        """
        n8n_nodes = n8n_workflow.get("nodes", [])
        connections = n8n_workflow.get("connections", {})
        wf_name = n8n_workflow.get("name", "n8n Workflow")

        name_to_id = {}
        canvas_nodes = []

        for idx, n in enumerate(n8n_nodes):
            n_id = n.get("id") or f"n{idx+1}"
            name = n.get("name", f"Node_{idx+1}")
            name_to_id[name] = n_id

            n_type = n.get("type", "")
            canvas_type = N8N_TO_CANVAS_TYPE_MAP.get(n_type, "action")
            pos = n.get("position", [100 + idx * 200, 100])

            params = n.get("parameters", {})
            desc = params.get("description") or f"Type: {n_type.split('.')[-1]}"

            canvas_nodes.append({
                "id": n_id,
                "type": canvas_type,
                "title": name,
                "desc": desc,
                "x": pos[0] if len(pos) > 0 else 100,
                "y": pos[1] if len(pos) > 1 else 100,
                "status": "idle",
                "config": params
            })

        canvas_edges = []
        edge_counter = 1

        for src_name, con_data in connections.items():
            src_id = name_to_id.get(src_name)
            if not src_id:
                continue

            main_outputs = con_data.get("main", [])
            for out_idx, target_list in enumerate(main_outputs):
                label = "True" if out_idx == 0 else "False" if out_idx == 1 else ""
                for tgt in target_list:
                    dst_name = tgt.get("node")
                    dst_id = name_to_id.get(dst_name)
                    if dst_id:
                        canvas_edges.append({
                            "id": f"e{edge_counter}",
                            "from": src_id,
                            "to": dst_id,
                            "label": label if len(main_outputs) > 1 else ""
                        })
                        edge_counter += 1

        logger.info("Reconstructed JARVIS Canvas graph from n8n Workflow '{}' ({} nodes, {} edges)", wf_name, len(canvas_nodes), len(canvas_edges))
        return {
            "name": wf_name,
            "nodes": canvas_nodes,
            "edges": canvas_edges
        }

    @staticmethod
    def topological_execution_order(canvas_graph: Dict[str, Any]) -> List[List[str]]:
        """
        Compute DAG execution levels (parallel groups) for canvas status updates.
        Returns a list of lists of node IDs e.g. [['n1'], ['n2', 'n3'], ['n4']].
        """
        nodes = canvas_graph.get("nodes", [])
        edges = canvas_graph.get("edges", [])

        in_degree = {n["id"]: 0 for n in nodes}
        adj = {n["id"]: [] for n in nodes}

        for e in edges:
            u, v = e.get("from"), e.get("to")
            if u in adj and v in in_degree:
                adj[u].append(v)
                in_degree[v] += 1

        queue = [n_id for n_id, deg in in_degree.items() if deg == 0]
        levels = []

        while queue:
            levels.append(list(queue))
            next_queue = []
            for u in queue:
                for v in adj[u]:
                    in_degree[v] -= 1
                    if in_degree[v] == 0:
                        next_queue.append(v)
            queue = next_queue

        return levels

    @staticmethod
    def generate_workflow_from_prompt(prompt: str) -> Dict[str, Any]:
        """
        Generate a JARVIS visual canvas workflow graph from natural language instruction.
        Example: "Create a workflow to organize my downloaded PDFs and summarize them"
        """
        logger.info("Generating visual workflow graph from prompt: '{}'", prompt)
        p_lower = prompt.lower()

        # PDF Organization & Summarization Workflow Pattern
        if "pdf" in p_lower or "download" in p_lower or "organize" in p_lower:
            return {
                "name": "PDF Scanner & Summarizer Workflow",
                "nodes": [
                    {
                        "id": "n1",
                        "type": "trigger",
                        "title": "File Watcher / Scheduled Trigger",
                        "desc": "Monitors Downloads folder for new .pdf files",
                        "x": 50,
                        "y": 120,
                        "status": "idle"
                    },
                    {
                        "id": "n2",
                        "type": "action",
                        "title": "PDF Parser & OCR",
                        "desc": "Extracts text content and metadata from PDF document",
                        "x": 300,
                        "y": 120,
                        "status": "idle"
                    },
                    {
                        "id": "n3",
                        "type": "condition",
                        "title": "Check Text Length",
                        "desc": "If text length > 500 characters",
                        "x": 550,
                        "y": 120,
                        "status": "idle"
                    },
                    {
                        "id": "n4",
                        "type": "llm",
                        "title": "JARVIS Executive Summarizer",
                        "desc": "Generates concise key bullet points summary",
                        "x": 800,
                        "y": 60,
                        "status": "idle"
                    },
                    {
                        "id": "n5",
                        "type": "action",
                        "title": "Move to PDF Archive Folder",
                        "desc": "Organizes processed PDF into data/pdf_archive/",
                        "x": 800,
                        "y": 180,
                        "status": "idle"
                    }
                ],
                "edges": [
                    {"id": "e1", "from": "n1", "to": "n2"},
                    {"id": "e2", "from": "n2", "to": "n3"},
                    {"id": "e3", "from": "n3", "to": "n4", "label": "True"},
                    {"id": "e4", "from": "n3", "to": "n5", "label": "False"},
                    {"id": "e5", "from": "n4", "to": "n5"}
                ]
            }

        # General Workstation & Automation Pattern
        return {
            "name": f"Workflow: {prompt[:30]}",
            "nodes": [
                {
                    "id": "n1",
                    "type": "trigger",
                    "title": "User Command Trigger",
                    "desc": f"Triggered by prompt: {prompt}",
                    "x": 60,
                    "y": 100,
                    "status": "idle"
                },
                {
                    "id": "n2",
                    "type": "action",
                    "title": "Execute Desktop Task",
                    "desc": "Performs desktop system action",
                    "x": 320,
                    "y": 100,
                    "status": "idle"
                },
                {
                    "id": "n3",
                    "type": "llm",
                    "title": "JARVIS Reflection & Output",
                    "desc": "Summarizes completion status and notifies user",
                    "x": 580,
                    "y": 100,
                    "status": "idle"
                }
            ],
            "edges": [
                {"id": "e1", "from": "n1", "to": "n2"},
                {"id": "e2", "from": "n2", "to": "n3"}
            ]
        }
