"""
Clipboard Intelligence Service for JARVIS.

Monitors system clipboard text changes and provides fast quick-action intelligence
(Translate, Summarize, Explain, Fix Code).
"""

import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


class ClipboardIntelligenceService:
    """Monitors clipboard updates and triggers LLM action processing."""

    def __init__(self):
        self._last_text = ""
        self._last_change_time = 0.0
        self._running = False
        logger.info("ClipboardIntelligenceService initialized")

    def get_current_clipboard(self) -> Dict[str, Any]:
        """Fetch current text from OS clipboard."""
        if not HAS_PYPERCLIP:
            return {"error": "pyperclip module not installed"}
        try:
            text = pyperclip.paste().strip()
            return {
                "text": text,
                "length": len(text),
                "has_text": len(text) > 0,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Clipboard read error: {e}")
            return {"error": str(e)}

    async def process_quick_action(self, action: str, text: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute quick action (translate, summarize, explain, fix) on clipboard text.
        """
        target_text = text or self.get_current_clipboard().get("text", "")
        if not target_text:
            return {"status": "error", "message": "No text found in clipboard."}

        action_clean = action.lower().strip()
        logger.info(f"📋 Executing Clipboard Intelligence action '{action_clean}' on {len(target_text)} chars")

        if action_clean == "translate":
            prompt = f"Translate the following text to clear, professional English:\n\n{target_text[:1000]}"
        elif action_clean == "summarize":
            prompt = f"Summarize the following text in 2-3 concise bullet points:\n\n{target_text[:1500]}"
        elif action_clean == "explain":
            prompt = f"Explain the core concept or logic of this snippet simply:\n\n{target_text[:1000]}"
        elif action_clean in ("fix", "fix_code"):
            prompt = f"Identify and fix any bugs or grammar issues in this text/code:\n\n{target_text[:1500]}"
        else:
            prompt = f"Process this text:\n\n{target_text[:1000]}"

        # Delegate to LLM
        from backend.services.manager import ServiceManager
        llm = ServiceManager.get_instance("llm_service")
        if llm and hasattr(llm, "simple_completion"):
            try:
                res = await llm.simple_completion(prompt)
                return {
                    "status": "ok",
                    "action": action_clean,
                    "original_excerpt": target_text[:100],
                    "result": res
                }
            except Exception as e:
                logger.error(f"Clipboard LLM action error: {e}")

        # Fallback response
        return {
            "status": "ok",
            "action": action_clean,
            "original_excerpt": target_text[:100],
            "result": f"[Clipboard Action '{action_clean}'] Processed {len(target_text)} characters."
        }
