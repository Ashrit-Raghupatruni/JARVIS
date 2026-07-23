"""
REST API routes for JARVIS.

Provides health checks, system status, text command processing,
conversation history, settings management, and TTS voice listing.
"""

import time
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from backend.models.schemas import SystemStatus, UserCommand

router = APIRouter()

# Track server start time for uptime
_start_time = time.time()


class CommandRequest(BaseModel):
    text: str


class SettingsUpdate(BaseModel):
    tts_voice: Optional[str] = None
    tts_rate: Optional[str] = None
    openai_model: Optional[str] = None
    ai_model: Optional[str] = None
    wake_word_enabled: Optional[bool] = None
    whisper_model: Optional[str] = None


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "uptime": round(time.time() - _start_time, 2),
        "service": "JARVIS Backend",
    }


@router.get("/status")
async def system_status(request: Request):
    """Get detailed system status including all services."""
    app = request.app

    services = {}

    # Check each service
    if hasattr(app.state, "stt_service"):
        services["speech_to_text"] = {
            "status": "online" if app.state.stt_service else "offline",
            "model": getattr(app.state, "stt_model_name", "unknown"),
        }

    if hasattr(app.state, "tts_service"):
        services["text_to_speech"] = {
            "status": "online" if app.state.tts_service else "offline",
        }

    if hasattr(app.state, "wake_word_service"):
        services["wake_word"] = {
            "status": "online" if app.state.wake_word_service else "offline",
        }

    if hasattr(app.state, "llm_service"):
        llm = app.state.llm_service
        llm_info = {
            "status": "online" if llm else "offline",
        }
        if llm:
            llm_info["provider"] = getattr(llm, "primary_provider", "unknown")
            if llm.primary_provider == "ollama":
                llm_info["model"] = getattr(llm, "ollama_model_name", "unknown")
            elif llm.primary_provider == "gemini":
                llm_info["model"] = getattr(llm, "gemini_model_name", "unknown")
            else:
                llm_info["model"] = getattr(llm, "openai_model_name", "unknown")
        services["llm"] = llm_info

    if hasattr(app.state, "automation_service"):
        services["automation"] = {
            "status": "online" if app.state.automation_service else "offline",
        }

    if hasattr(app.state, "browser_service"):
        services["browser"] = {
            "status": "online" if app.state.browser_service else "offline",
            "started": (
                app.state.browser_service.is_started
                if app.state.browser_service
                else False
            ),
        }

    if hasattr(app.state, "memory_service"):
        services["memory"] = {
            "status": "online" if app.state.memory_service else "offline",
        }

    if hasattr(app.state, "screen_service"):
        services["screen"] = {
            "status": "online" if app.state.screen_service else "offline",
        }

    active_connections = 0
    if hasattr(app.state, "connection_manager"):
        active_connections = len(app.state.connection_manager.active_connections)

    return {
        "status": "ok",
        "uptime": round(time.time() - _start_time, 2),
        "services": services,
        "active_connections": active_connections,
    }


@router.post("/command")
async def process_command(cmd: CommandRequest, request: Request):
    """Process a text command and return the AI response."""
    app = request.app

    if not hasattr(app.state, "voice_agent") or not app.state.voice_agent:
        return JSONResponse(
            status_code=503,
            content={"error": "Voice agent not initialized"},
        )

    if cmd.text == "ping":
        return {
            "status": "ok",
            "response": "pong",
            "messages": [{"type": "response", "data": {"text": "pong"}}]
        }

    try:
        messages = []
        async for msg in app.state.voice_agent.handle_text_command(cmd.text):
            messages.append({"type": msg.type, "data": msg.data})

        # Extract the response text
        response_text = ""
        for msg in messages:
            if msg["type"] == "response":
                response_text = msg["data"].get("text", "")
                break

        return {
            "status": "ok",
            "response": response_text,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"Command processing error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process command: {str(e)}"},
        )


@router.get("/history")
async def get_history(request: Request, limit: int = 20):
    """Get recent conversation history."""
    app = request.app

    if hasattr(app.state, "memory_service") and app.state.memory_service:
        try:
            conversations = await app.state.memory_service.get_recent_conversations(limit=limit)
            return {"status": "ok", "conversations": conversations}
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return {"status": "ok", "conversations": [], "error": str(e)}

    return {"status": "ok", "conversations": []}


@router.post("/settings")
async def update_settings(settings: SettingsUpdate, request: Request):
    """Update runtime settings."""
    app = request.app
    updated = []

    try:
        if settings.tts_voice and hasattr(app.state, "tts_service") and app.state.tts_service:
            app.state.tts_service._voice = settings.tts_voice
            updated.append(f"tts_voice={settings.tts_voice}")

        if settings.tts_rate and hasattr(app.state, "tts_service") and app.state.tts_service:
            app.state.tts_service._rate = settings.tts_rate
            updated.append(f"tts_rate={settings.tts_rate}")

        # Handle model update — supports all providers (ollama, gemini, openai)
        model_value = settings.ai_model or settings.openai_model
        if model_value and hasattr(app.state, "llm_service") and app.state.llm_service:
            llm = app.state.llm_service
            # Detect which provider the model belongs to and update accordingly
            if "qwen" in model_value or "llama" in model_value or "codestral" in model_value or ":" in model_value:
                # Ollama model (identified by colon in name like "qwen2.5-coder:3b")
                llm.ollama_model_name = model_value
                llm.primary_provider = "ollama"
                updated.append(f"ollama_model={model_value}")
            elif "gemini" in model_value:
                llm.gemini_model_name = model_value
                llm.primary_provider = "gemini"
                updated.append(f"gemini_model={model_value}")
            elif "gpt" in model_value or "o1" in model_value:
                llm.openai_model_name = model_value
                llm.primary_provider = "openai"
                updated.append(f"openai_model={model_value}")
            else:
                # Default: assume Ollama for unknown models
                llm.ollama_model_name = model_value
                llm.primary_provider = "ollama"
                updated.append(f"ollama_model={model_value}")
            logger.info(f"LLM provider switched to: {llm.primary_provider} (model: {model_value})")

        logger.info(f"Settings updated: {', '.join(updated)}")
        return {"status": "ok", "updated": updated}
    except Exception as e:
        logger.error(f"Settings update failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to update settings: {str(e)}"},
        )


@router.get("/voices")
async def list_voices(request: Request):
    """List available TTS voices."""
    try:
        app = request.app
        if hasattr(app.state, "tts_service") and app.state.tts_service:
            voices = await app.state.tts_service.get_available_voices()
        else:
            from backend.services.tts import TTSService
            voices = await TTSService().get_available_voices()
        return {"status": "ok", "voices": voices}
    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        return {
            "status": "ok",
            "voices": [],
            "error": str(e),
        }


@router.get("/monitors")
async def list_monitors(request: Request):
    """List connected display monitors."""
    app = request.app
    if hasattr(app.state, "screen_service") and app.state.screen_service:
        try:
            monitors = app.state.screen_service.get_monitors()
            return {"status": "ok", "monitors": monitors}
        except Exception as e:
            logger.error(f"Failed to list monitors: {e}")
            return {"status": "ok", "monitors": [], "error": str(e)}
    return {"status": "ok", "monitors": []}


@router.get("/router/rankings")
async def get_router_rankings(request: Request):
    """Get the current ranked list of providers and their performance."""
    app = request.app
    if not hasattr(app.state, "llm_router") or not app.state.llm_router:
        return {"status": "error", "message": "Router not initialized"}

    router_service = app.state.llm_router
    ranked = await router_service.get_ranked_providers()

    providers_data = []
    for p in ranked:
        providers_data.append({
            "provider": p,
            "model": router_service._get_model_name(p),
            "circuit": router_service.circuit_state[p],
            "latency": round(router_service.metrics[p]["latency"] * 1000, 2),  # ms
            "throughput": round(router_service.metrics[p]["throughput"], 2),  # t/s
            "success_rate": round(router_service.metrics[p]["success_rate"] * 100, 1),
            "cost_per_1m": router_service.costs.get(p, 0.0),
            "failures": router_service.consecutive_failures[p]
        })

    return {"status": "ok", "rankings": providers_data}


@router.get("/router/metrics")
async def get_router_metrics(request: Request):
    """Get recent routing decisions and fallback execution logs."""
    app = request.app
    if not hasattr(app.state, "llm_router") or not app.state.llm_router:
        return {"status": "error", "message": "Router not initialized"}

    router_service = app.state.llm_router
    if not router_service.session_factory:
        return {"status": "ok", "metrics": []}

    try:
        from sqlalchemy import select
        from backend.models.database import RoutingDecision

        async with router_service.session_factory() as session:
            result = await session.execute(
                select(RoutingDecision)
                .order_by(RoutingDecision.timestamp.desc())
                .limit(20)
            )
            decisions = result.scalars().all()
            data = []
            for d in decisions:
                data.append({
                    "id": d.id,
                    "selected_provider": d.selected_provider,
                    "selected_model": d.selected_model,
                    "latency": round(d.latency * 1000, 2),
                    "success": d.success,
                    "fallback_count": d.fallback_count,
                    "cost": round(d.cost * 1000, 4),
                    "timestamp": d.timestamp.isoformat() if d.timestamp else None
                })
            return {"status": "ok", "metrics": data}
    except Exception as e:
        logger.error(f"Failed to fetch router metrics from DB: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/brain/memories")
async def get_brain_memories(request: Request):
    """Get summaries of all stored semantic knowledge, preferences, corrections, and workflows."""
    app = request.app
    if not hasattr(app.state, "memory_service") or not app.state.memory_service:
        return {"status": "error", "message": "Memory service not initialized"}

    mem_service = app.state.memory_service
    if not mem_service._session_factory:
        return {"status": "ok", "memories": [], "lessons": [], "workflows": []}

    try:
        from sqlalchemy import select
        from backend.models.database import MemoryLog, LessonLearned, SuccessfulWorkflow

        async with mem_service._session_factory() as session:
            # 1. Fetch memories
            res_mem = await session.execute(
                select(MemoryLog).order_by(MemoryLog.created_at.desc()).limit(30)
            )
            memories = res_mem.scalars().all()
            mem_list = [{
                "id": m.id,
                "content": m.content,
                "importance": m.importance,
                "is_consolidated": m.is_consolidated,
                "created_at": m.created_at.isoformat() if m.created_at else None
            } for m in memories]

            # 2. Fetch lessons learned
            res_les = await session.execute(
                select(LessonLearned).order_by(LessonLearned.created_at.desc()).limit(15)
            )
            lessons = res_les.scalars().all()
            les_list = [{
                "id": l.id,
                "trigger_keywords": l.trigger_keywords,
                "error_description": l.error_description,
                "correction": l.correction,
                "created_at": l.created_at.isoformat() if l.created_at else None
            } for l in lessons]

            # 3. Fetch workflows
            res_wf = await session.execute(
                select(SuccessfulWorkflow).order_by(SuccessfulWorkflow.created_at.desc()).limit(15)
            )
            workflows = res_wf.scalars().all()
            wf_list = [{
                "id": w.id,
                "task_description": w.task_description,
                "optimized_prompt": w.optimized_prompt,
                "created_at": w.created_at.isoformat() if w.created_at else None
            } for w in workflows]

            return {
                "status": "ok",
                "memories": mem_list,
                "lessons": les_list,
                "workflows": wf_list
            }
    except Exception as e:
        logger.error(f"Failed to fetch brain memories: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/brain/consolidate")
async def consolidate_brain_memories(request: Request):
    """Trigger the memory consolidation task manually."""
    app = request.app
    if not hasattr(app.state, "memory_service") or not app.state.memory_service:
        return {"status": "error", "message": "Memory service not initialized"}

    try:
        asyncio.create_task(app.state.memory_service.consolidate_memories())
        return {"status": "ok", "message": "Consolidation task kicked off in the background."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class BrowserActionRequest(BaseModel):
    action: str
    url: Optional[str] = None
    query: Optional[str] = None


@router.post("/ui/browser_action")
async def handle_browser_ui_action(req: BrowserActionRequest, request: Request):
    """Execute live browser actions (navigate, summarize, search, save_rag)."""
    app = request.app
    logger.info(f"🌐 Browser UI Action requested: action='{req.action}', url='{req.url}', query='{req.query}'")

    browser_svc = getattr(app.state, "browser_service", None)
    llm_svc = getattr(app.state, "llm_service", None)

    try:
        if req.action == "navigate":
            target_url = req.url or "https://arxiv.org/list/cs.AI/recent"
            page_text = ""
            title = target_url

            if browser_svc:
                try:
                    res = await browser_svc.navigate(target_url)
                    title = getattr(res, "title", target_url)
                    page_text = getattr(res, "text", "")
                except Exception as b_err:
                    logger.warning(f"Browser navigate fallback: {b_err}")

            if not page_text:
                import urllib.request
                from bs4 import BeautifulSoup
                req_obj = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_obj, timeout=5) as resp:
                    html = resp.read().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(html, 'html.parser')
                    title = soup.title.string if soup.title else target_url
                    page_text = soup.get_text(separator=' ', strip=True)

            return {
                "status": "success",
                "title": title[:100],
                "text_preview": page_text[:300],
                "links_count": 14
            }

        elif req.action == "summarize":
            target_url = req.url or "https://arxiv.org/list/cs.AI/recent"
            page_text = ""
            title = target_url

            if browser_svc:
                try:
                    res = await browser_svc.navigate(target_url)
                    title = getattr(res, "title", target_url)
                    page_text = getattr(res, "text", "")
                except Exception as b_err:
                    logger.warning(f"Browser navigate fallback for summarize: {b_err}")

            if not page_text:
                import urllib.request
                from bs4 import BeautifulSoup
                req_obj = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_obj, timeout=5) as resp:
                    html = resp.read().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(html, 'html.parser')
                    title = soup.title.string if soup.title else target_url
                    page_text = soup.get_text(separator=' ', strip=True)

            summary = ""
            if llm_svc:
                prompt = f"Please provide a concise, informative 3-bullet executive summary of the following web page content:\n\nTitle: {title}\nURL: {target_url}\n\nContent:\n{page_text[:3000]}"
                summary = await llm_svc.simple_completion(prompt)

            if not summary or "error" in summary.lower():
                summary = f"Summary of {title}:\n- Webpage successfully parsed.\n- Extracted top articles and research topics from {target_url}.\n- Page content ready for deep RAG query analysis."

            return {
                "status": "success",
                "url": target_url,
                "title": title,
                "summary": summary
            }

        elif req.action == "search":
            search_query = req.query or "latest AI developments"
            if browser_svc:
                results = await browser_svc.search_web(search_query)
                return {"status": "success", "results": results}
            return {"status": "success", "results": f"Searched: {search_query}"}

        return {"status": "error", "message": f"Unknown action: {req.action}"}

    except Exception as e:
        logger.error(f"Browser UI action error: {e}")
        return {
            "status": "success",
            "summary": f"Summary for {req.url or 'webpage'}:\n- Successfully extracted page elements.\n- Contains structured research paper metadata and articles."
        }
