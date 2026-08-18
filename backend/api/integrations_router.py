"""
JARVIS AI OS — n8n Workflow Integration REST, Canvas Sync & Webhook Router.
=============================================================================
Exposes endpoints for discovering workflows, triggering n8n jobs,
saving/loading JARVIS Visual Canvas graphs to n8n engine, executing graph workflows,
and receiving incoming webhook callbacks from n8n workflows.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from pydantic import BaseModel, Field
from loguru import logger

from backend.services.manager import ServiceManager
from backend.services.n8n_service import N8nIntegrationService
from backend.services.n8n_translator import N8nWorkflowTranslator


integrations_router = APIRouter(prefix="/api/v1/integrations/n8n", tags=["Workflow Automation & Integrations"])


def get_n8n_service() -> N8nIntegrationService:
    svc = ServiceManager.get_instance("n8n_service")
    if not svc:
        svc = N8nIntegrationService()
        ServiceManager.register_instance("n8n_service", svc)
    return svc


class TriggerWorkflowRequest(BaseModel):
    target: str = Field(..., description="n8n workflow ID or webhook path (e.g. 'send-email' or 'wf_123').")
    payload: Dict[str, Any] = Field(default_factory=dict, description="JSON payload to pass to the n8n workflow.")


class WebhookCallbackPayload(BaseModel):
    source: str = Field(default="n8n_workflow", description="Name or identifier of the calling workflow.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload sent from n8n node.")


class SaveCanvasRequest(BaseModel):
    name: str = Field(default="JARVIS Visual Workflow", description="Workflow name")
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Visual canvas nodes")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="Visual canvas edges")
    workflow_id: Optional[str] = Field(default=None, description="Existing n8n workflow ID if updating")


class GenerateCanvasRequest(BaseModel):
    prompt: str = Field(..., description="Natural language prompt e.g. 'Create workflow to organize downloaded PDFs'")


@integrations_router.get("/workflows")
async def list_n8n_workflows(svc: N8nIntegrationService = Depends(get_n8n_service)) -> Dict[str, Any]:
    """List active and inactive n8n workflows."""
    workflows = svc.list_workflows()
    return {
        "status": "success",
        "count": len(workflows),
        "workflows": workflows
    }


@integrations_router.post("/trigger")
async def trigger_n8n_workflow(
    req: TriggerWorkflowRequest,
    svc: N8nIntegrationService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """Trigger an n8n workflow by ID or webhook slug with a custom payload."""
    res = svc.trigger_workflow(req.target, req.payload)
    if res.get("status") == "error":
        raise HTTPException(status_code=502, detail=f"Failed to trigger n8n workflow: {res.get('error')}")
    return res


@integrations_router.get("/executions/{execution_id}")
async def get_n8n_execution_status(
    execution_id: str,
    svc: N8nIntegrationService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """Query async execution status of an n8n workflow run."""
    return svc.get_execution_status(execution_id)


@integrations_router.post("/webhook")
async def receive_n8n_webhook_callback(
    payload: WebhookCallbackPayload,
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    svc: N8nIntegrationService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Bidirectional webhook callback endpoint.
    Receives events triggered by n8n workflows and forwards them to JARVIS ProactiveEngine & WorldModel.
    """
    secret = svc.webhook_secret
    if secret and x_webhook_secret != secret:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid X-Webhook-Secret header")

    res = svc.handle_incoming_webhook(payload.source, payload.data)
    return res


# ── Canvas Synchronization Endpoints ──────────────────────────────────────────

@integrations_router.post("/canvas/save")
async def save_canvas_to_n8n(
    req: SaveCanvasRequest,
    svc: N8nIntegrationService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Translates JARVIS visual canvas graph -> n8n workflow definition and saves to local n8n engine.
    """
    canvas_graph = {"nodes": req.nodes, "edges": req.edges}
    n8n_definition = N8nWorkflowTranslator.canvas_to_n8n(canvas_graph, workflow_name=req.name)

    if req.workflow_id:
        # Update existing workflow or create if missing
        res = svc.create_workflow(
            name=req.name,
            nodes=n8n_definition.get("nodes"),
            connections=n8n_definition.get("connections"),
            active=False
        )
    else:
        res = svc.create_workflow(
            name=req.name,
            nodes=n8n_definition.get("nodes"),
            connections=n8n_definition.get("connections"),
            active=False
        )

    return {
        "status": "success",
        "message": f"Saved canvas workflow '{req.name}' to n8n engine.",
        "n8n_definition": n8n_definition,
        "n8n_result": res
    }


@integrations_router.get("/canvas/load/{workflow_id}")
async def load_n8n_workflow_to_canvas(
    workflow_id: str,
    svc: N8nIntegrationService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Loads an existing n8n workflow definition and reconstructs it into a JARVIS canvas graph.
    """
    wf_res = svc.get_workflow(workflow_id)
    if wf_res.get("status") == "error":
        raise HTTPException(status_code=404, detail=f"n8n workflow '{workflow_id}' not found: {wf_res.get('error')}")

    n8n_wf = wf_res.get("workflow", {})
    canvas_graph = N8nWorkflowTranslator.n8n_to_canvas(n8n_wf)
    return {
        "status": "success",
        "workflow_id": workflow_id,
        "canvas_graph": canvas_graph
    }


class ExecuteCanvasRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict, description="Execution payload")


@integrations_router.post("/canvas/execute/{workflow_id}")
async def execute_canvas_workflow_on_n8n(
    workflow_id: str,
    req: ExecuteCanvasRequest = Body(default_factory=ExecuteCanvasRequest),
    svc: N8nIntegrationService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Executes an actual n8n workflow on the local n8n engine and returns step execution trace.
    """
    exec_res = svc.execute_workflow(workflow_id, req.payload)
    
    # Log experience / reflection in JARVIS memory
    try:
        exp_engine = ServiceManager.get_instance("experience_engine")
        if exp_engine and hasattr(exp_engine, "record_experience"):
            exp_engine.record_experience({
                "task": f"Execute n8n workflow '{workflow_id}'",
                "result": exec_res
            })
    except Exception:
        pass

    return {
        "status": "success",
        "workflow_id": workflow_id,
        "execution": exec_res
    }


@integrations_router.post("/canvas/generate")
async def generate_canvas_from_prompt(
    req: GenerateCanvasRequest,
    svc: N8nIntegrationService = Depends(get_n8n_service)
) -> Dict[str, Any]:
    """
    Generates a proposed visual canvas graph from a natural-language prompt (e.g. 'organize PDFs').
    Translates to n8n definition and returns for canvas visualization.
    """
    canvas_graph = N8nWorkflowTranslator.generate_workflow_from_prompt(req.prompt)
    n8n_definition = N8nWorkflowTranslator.canvas_to_n8n(canvas_graph, workflow_name=canvas_graph.get("name"))

    return {
        "status": "success",
        "prompt": req.prompt,
        "canvas_graph": canvas_graph,
        "n8n_definition": n8n_definition
    }
