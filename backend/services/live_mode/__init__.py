"""
JARVIS AI OS Live Mode Engine Package.

Provides dedicated real-time continuous desktop observation, step-by-step guidance,
proactive collaboration, smart form auto-filling, and human-in-the-loop interlocks.
"""

from backend.services.live_mode.live_engine import LiveModeEngine, LiveContextFrame
from backend.services.live_mode.form_assistant import FormAssistant

__all__ = ["LiveModeEngine", "LiveContextFrame", "FormAssistant"]
