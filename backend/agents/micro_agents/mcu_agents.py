"""
JARVIS Personal AI OS - The Complete 21 MCU J.A.R.V.I.S. Micro-Agent Registry.
Implements the 21 specialized autonomous agents driving Tony Stark's AI OS vision.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from backend.agents.micro_agents.base_agent import BaseMicroAgent, MicroAgentMessage


class VoiceAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("VoiceAgent", "Low-power always listening, streaming STT/TTS voice duplex pipeline.", event_bus)

    async def process_message(self, message: MicroAgentMessage) -> Optional[MicroAgentMessage]:
        return MicroAgentMessage(self.name, message.sender, f"Voice audio stream processed: {message.content}", "telemetry")


class ConversationAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("ConversationAgent", "Natural language understanding, MCU J.A.R.V.I.S. Marvel personality & situational tone.", event_bus)


class MemoryAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("MemoryAgent", "3-tier human-like memory (Short-term, Episodic session, Long-term semantic knowledge graph).", event_bus)


class PlanningAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("PlanningAgent", "Hierarchical goal decomposition, action graph planning, and runtime self-healing recovery.", event_bus)


class VisionAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("VisionAgent", "Multimodal perception, live screen OCR, spatial monitor topology, and webcam visual tracking.", event_bus)

    async def process_message(self, message: MicroAgentMessage) -> Optional[MicroAgentMessage]:
        from backend.services.manager import ServiceManager
        vision_svc = ServiceManager.get_instance("vision_service")
        if vision_svc:
            try:
                monitors = vision_svc.get_multi_monitor_layout()
                windows = vision_svc.get_window_hierarchy()
                content = f"Vision layout scanned: {len(monitors)} monitor(s) and {len(windows)} active window(s) detected."
            except Exception as e:
                content = f"Vision scan failed: {e}"
        else:
            content = "Vision Service unavailable."
        return MicroAgentMessage(self.name, message.sender, content, "response")


class DesktopControlAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("DesktopControlAgent", "Win32 UIA accessibility tree, mouse/keyboard automation, window switching, and process management.", event_bus)


class BrowserAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("BrowserAgent", "Headless Playwright browser automation perceive-act-observe loops and form filling.", event_bus)


class CodingAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("CodingAgent", "AST code analysis, refactoring, module generation, git/docker management, and sandbox execution.", event_bus)

    async def process_message(self, message: MicroAgentMessage) -> Optional[MicroAgentMessage]:
        from backend.services.manager import ServiceManager
        dev_service = ServiceManager.get_instance("self_development_service")
        if dev_service:
            try:
                scan = dev_service.scan_project_structure()
                content = f"Project structure scanned: {scan.get('python_modules_scanned', 0)} python modules indexed."
            except Exception as e:
                content = f"Coding Agent error: {e}"
        else:
            content = "Self-Development Service unavailable."
        return MicroAgentMessage(self.name, message.sender, content, "response")


class ResearchAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("ResearchAgent", "Web search orchestration, RAG document vector querying, and paper summarization.", event_bus)

    async def process_message(self, message: MicroAgentMessage) -> Optional[MicroAgentMessage]:
        from backend.services.manager import ServiceManager
        research_svc = ServiceManager.get_instance("research_service")
        if research_svc:
            try:
                query = message.payload.get("query", message.content)
                res = await research_svc.search_and_summarize(query)
                content = f"Research completed: {res}"
            except Exception as e:
                content = f"Research failed: {e}"
        else:
            from backend.agents.langgraph_agent.tools import fallback_ddg_search
            try:
                res = await fallback_ddg_search(message.content)
                content = f"Research search result fallback:\n{res}"
            except Exception as e:
                content = f"Research fallback failed: {e}"
        return MicroAgentMessage(self.name, message.sender, content, "response")


class AutomationAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("AutomationAgent", "Event-driven, sensor-based, location-based, and schedule-based proactive background automation.", event_bus)


class CalendarAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("CalendarAgent", "User schedule management, meeting timelines, and daily agenda forecasting.", event_bus)


class ReminderAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("ReminderAgent", "Time-based task reminders, assignment deadlines, and follow-up prompts.", event_bus)


class NotificationAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("NotificationAgent", "Native desktop toasts, mobile push notifications, and priority alert filtering.", event_bus)


class SecurityAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("SecurityAgent", "Biometric fusion authentication (128-d Face ID + Voice ID), RBAC rules, and dangerous command interlocks.", event_bus)


class MobileAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("MobileAgent", "Android APK Mission Control sync, telemetry stream, approval gatekeeper, and remote commands.", event_bus)


class DeviceAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("DeviceAgent", "Hardware metric telemetry (CPU, RAM, GPU, Battery, Disk, WASAPI audio volume).", event_bus)


class LearningAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("LearningAgent", "Task experience tracing, reflection evaluation, and strategy memory confidence updating.", event_bus)


class EmotionAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("EmotionAgent", "User stress, fatigue, excitement, and confidence detection from speech cadence and typing rhythm.", event_bus)


class ContextAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("ContextAgent", "Central desktop world model state (active window, browser URL, clipboard text, active workflow).", event_bus)


class HealthAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("HealthAgent", "System operational health monitoring, component latency tracking, and user fatigue alerts.", event_bus)


class SelfDiagnosticAgent(BaseMicroAgent):
    def __init__(self, event_bus=None):
        super().__init__("SelfDiagnosticAgent", "Automated self-health diagnostic audits across all 21 micro-agents and service auto-restart.", event_bus)


ALL_MCU_AGENTS = [
    VoiceAgent,
    ConversationAgent,
    MemoryAgent,
    PlanningAgent,
    VisionAgent,
    DesktopControlAgent,
    BrowserAgent,
    CodingAgent,
    ResearchAgent,
    AutomationAgent,
    CalendarAgent,
    ReminderAgent,
    NotificationAgent,
    SecurityAgent,
    MobileAgent,
    DeviceAgent,
    LearningAgent,
    EmotionAgent,
    ContextAgent,
    HealthAgent,
    SelfDiagnosticAgent
]
