"""
REST API routes for JARVIS.

Provides health checks, system status, text command processing,
conversation history, settings management, and TTS voice listing.
"""

import time
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
        services["llm"] = {
            "status": "online" if app.state.llm_service else "offline",
        }

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

        if settings.openai_model and hasattr(app.state, "llm_service") and app.state.llm_service:
            app.state.llm_service._model = settings.openai_model
            updated.append(f"openai_model={settings.openai_model}")

        logger.info(f"Settings updated: {', '.join(updated)}")
        return {"status": "ok", "updated": updated}
    except Exception as e:
        logger.error(f"Settings update failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to update settings: {str(e)}"},
        )


@router.get("/voices")
async def list_voices():
    """List available TTS voices."""
    try:
        from backend.services.tts import TTSService

        voices = await TTSService.get_available_voices()
        return {"status": "ok", "voices": voices}
    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        return {
            "status": "ok",
            "voices": [],
            "error": str(e),
        }
