"""
JARVIS AI OS — n8n Function Calling Tools for Planner & AI Models.
===================================================================
Provides mandatory tool execution functions for ToolRegistry:
- n8n_list_workflows
- n8n_get_workflow
- n8n_execute_workflow
- n8n_create_workflow
- n8n_activate_workflow
- n8n_deactivate_workflow
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.services.manager import ServiceManager
from backend.services.n8n_service import N8nIntegrationService


def _get_n8n_service() -> N8nIntegrationService:
    svc = ServiceManager.get_instance("n8n_service")
    if not svc:
        svc = N8nIntegrationService()
        ServiceManager.register_instance("n8n_service", svc)
    return svc


def n8n_list_workflows() -> Dict[str, Any]:
    """
    List all active and inactive n8n automation workflows registered on the local n8n instance.
    """
    svc = _get_n8n_service()
    workflows = svc.list_workflows()
    return {
        "status": "success",
        "count": len(workflows),
        "workflows": workflows
    }


def n8n_get_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    Fetch node graph details and parameters for a specific n8n workflow ID.
    """
    svc = _get_n8n_service()
    return svc.get_workflow(workflow_id)


def n8n_execute_workflow(target: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute an n8n workflow by workflow ID or webhook slug with custom JSON parameters.
    """
    svc = _get_n8n_service()
    payload = payload or {}
    logger.info("Executing LLM tool n8n_execute_workflow for target '{}' with payload keys {}", target, list(payload.keys()))
    return svc.execute_workflow(target, payload)


def n8n_create_workflow(
    name: str,
    nodes: Optional[List[Dict[str, Any]]] = None,
    connections: Optional[Dict[str, Any]] = None,
    active: bool = False
) -> Dict[str, Any]:
    """
    Create a new n8n workflow graph on the local n8n engine.
    """
    svc = _get_n8n_service()
    return svc.create_workflow(name=name, nodes=nodes, connections=connections, active=active)


def n8n_activate_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    Activate an n8n workflow by workflow ID.
    """
    svc = _get_n8n_service()
    return svc.activate_workflow(workflow_id)


def n8n_deactivate_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    Deactivate an n8n workflow by workflow ID.
    """
    svc = _get_n8n_service()
    return svc.deactivate_workflow(workflow_id)
