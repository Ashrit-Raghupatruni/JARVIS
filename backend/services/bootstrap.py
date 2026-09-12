"""
JARVIS Application Bootstrap and Service Registration.

Provides modular, lightweight initialization for core essential services at startup,
and lazy-loading factory registration for all optional/heavy subsystems.
"""

import asyncio
from typing import Optional, Any
from loguru import logger

from backend.config import get_settings
from backend.utils.event_bus import EventBus
from backend.services.manager import ServiceManager


def bootstrap_core_services(app: Any, event_bus: Optional[EventBus] = None) -> EventBus:
    """
    Initialize only the essential, non-deferrable core services required for basic operation.
    Zero external network overhead, instant startup.
    """
    if event_bus is None:
        event_bus = EventBus()

    from backend.utils.logger import register_event_bus_sink
    register_event_bus_sink(event_bus)

    from backend.agents.context_manager import SharedContextManager
    from backend.utils.task_queue import AsyncTaskQueue
    from backend.services.config_manager import ConfigurationManager

    context_manager = SharedContextManager(event_bus)
    task_queue = AsyncTaskQueue(event_bus)
    task_queue.start()
    config_manager = ConfigurationManager(event_bus)

    app.state.event_bus = event_bus
    app.state.context_manager = context_manager
    app.state.task_queue = task_queue
    app.state.config_manager = config_manager
    app.state.service_manager = ServiceManager

    # Security & Safety Core (Fail-closed, zero latency)
    from backend.services.security.vault import CredentialVault
    from backend.services.security.sandbox import SecuritySandbox
    from backend.services.security.rbac import SecurityOrchestrator
    from backend.services.safety import SafetyService

    credential_vault = CredentialVault()
    security_sandbox = SecuritySandbox()
    security_orchestrator = SecurityOrchestrator(event_bus)
    safety_service = SafetyService()

    app.state.credential_vault = credential_vault
    app.state.security_sandbox = security_sandbox
    app.state.security_orchestrator = security_orchestrator
    app.state.safety_service = safety_service

    ServiceManager.register_instance("credential_vault", credential_vault)
    ServiceManager.register_instance("security_sandbox", security_sandbox)
    ServiceManager.register_instance("security_orchestrator", security_orchestrator)
    ServiceManager.register_instance("safety_service", safety_service)

    # Fast Intent Router Core
    from backend.services.fast_intent_router import fast_intent_router
    app.state.fast_intent_router = fast_intent_router
    ServiceManager.register_instance("fast_intent_router", fast_intent_router)

    from backend.api.websocket import manager as connection_manager
    app.state.connection_manager = connection_manager

    return event_bus


def register_lazy_factories(event_bus: EventBus, connection_manager: Optional[Any] = None) -> None:
    """
    Register on-demand factories for all optional, heavy, and domain subsystems.
    None of these services are instantiated until explicitly requested.
    """
    settings = get_settings()

    # 1. LLM Service (Deferred lazy instantiation)
    def _make_llm_service():
        from backend.services.llm import LLMService
        svc = LLMService()
        provider = settings.LLM_PROVIDER or "gemini"
        logger.info(f"✓ LLM service lazily instantiated (provider: {provider})")
        return svc
    ServiceManager.register_factory("llm_service", _make_llm_service)

    # 2. Autonomous Agent Ecosystem
    def _make_agent_ecosystem():
        from backend.services.agent_ecosystem import AgentEcosystemService
        return AgentEcosystemService(event_bus=event_bus, connection_manager=connection_manager)
    ServiceManager.register_factory("agent_ecosystem", _make_agent_ecosystem)

    # 3. Checkpoint & KV Pruning
    def _make_checkpoint_service():
        from backend.services.long_horizon_checkpoint import LongHorizonCheckpointService
        svc = LongHorizonCheckpointService()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(svc.initialize())
        except (RuntimeError, AttributeError):
            pass
        return svc
    ServiceManager.register_factory("checkpoint_service", _make_checkpoint_service)

    def _make_kv_pruner():
        from backend.services.kv_cache_pruner import KVCachePruner
        return KVCachePruner()
    ServiceManager.register_factory("kv_pruner", _make_kv_pruner)

    # 4. World Model
    def _make_world_model():
        from backend.services.world_model import WorldModel
        return WorldModel(event_bus=event_bus)
    ServiceManager.register_factory("world_model", _make_world_model)

    # 5. Biometrics & Vision
    def _make_face_biometrics():
        from backend.services.face_biometrics import FaceBiometricsService
        return FaceBiometricsService()
    ServiceManager.register_factory("face_biometrics_service", _make_face_biometrics)

    def _make_screen_service():
        from backend.services.screen import ScreenService
        return ScreenService()
    ServiceManager.register_factory("screen_service", _make_screen_service)

    def _make_vision_service():
        from backend.services.vision_service import VisionService
        return VisionService()
    ServiceManager.register_factory("vision_service", _make_vision_service)

    def _make_hand_control():
        from backend.services.hand_control_service import HandControlService
        return HandControlService()
    ServiceManager.register_factory("hand_control_service", _make_hand_control)

    # 6. Audio Subsystems (VoiceManager, STT, TTS, WakeWord, AudioDevices, Clap)
    def _make_audio_device_manager():
        from backend.services.voice import AudioDeviceManager
        return AudioDeviceManager()
    ServiceManager.register_factory("audio_device_manager", _make_audio_device_manager)

    def _make_stt_service():
        from backend.services.voice import STTManager
        return STTManager()
    ServiceManager.register_factory("stt_service", _make_stt_service)

    def _make_tts_service():
        from backend.services.voice import TTSManager
        return TTSManager()
    ServiceManager.register_factory("tts_service", _make_tts_service)

    def _make_wake_word_service():
        from backend.services.voice import WakeWordManager
        return WakeWordManager()
    ServiceManager.register_factory("wake_word_service", _make_wake_word_service)

    def _make_clap_service():
        from backend.services.clap import ClapService
        def handle_clap_event(mode):
            logger.info(f"Double clap event triggered (mode={mode}). Restoring JARVIS desktop window...")
            try:
                auto_svc = ServiceManager.get_instance("automation_service")
                if auto_svc and hasattr(auto_svc, "focus_window"):
                    auto_svc.focus_window("JARVIS")
            except Exception as e:
                logger.warning(f"Could not focus JARVIS window on clap: {e}")
        cs = ClapService(on_clap_detected=handle_clap_event)
        cs.start()
        return cs
    ServiceManager.register_factory("clap_service", _make_clap_service)

    # 7. Automation & RPA
    def _make_automation_orchestrator():
        from backend.services.automation import AutomationOrchestrator
        return AutomationOrchestrator()
    ServiceManager.register_factory("automation_orchestrator", _make_automation_orchestrator)

    def _make_automation_service():
        from backend.services.automation import AutomationService
        return AutomationService()
    ServiceManager.register_factory("automation_service", _make_automation_service)
    ServiceManager.register_factory("automation", _make_automation_service)
    ServiceManager.register_factory("desktop_executor", _make_automation_service)

    def _make_uia_engine():
        from backend.services.automation import UIAPerceptionEngine
        return UIAPerceptionEngine()
    ServiceManager.register_factory("uia_engine", _make_uia_engine)
    ServiceManager.register_factory("uia_perception_engine", _make_uia_engine)

    def _make_desktop_automation():
        from backend.services.automation import AutomationOrchestrator
        return AutomationOrchestrator()
    ServiceManager.register_factory("desktop_automation_service", _make_desktop_automation)

    def _make_browser_service():
        from backend.services.automation import BrowserExecutor
        return BrowserExecutor()
    ServiceManager.register_factory("browser_service", _make_browser_service)
    ServiceManager.register_factory("browser_executor", _make_browser_service)

    def _make_action_verifier():
        from backend.services.automation import ActionExecutionVerifier
        return ActionExecutionVerifier()
    ServiceManager.register_factory("action_verifier", _make_action_verifier)

    def _make_task_queue_service():
        from backend.services.task_queue import TaskQueueService
        return TaskQueueService()
    ServiceManager.register_factory("task_queue_service", _make_task_queue_service)

    # 8. Developer & Research Subsystems
    def _make_developer_assistant():
        from backend.services.developer_assistant import DeveloperAssistantService
        return DeveloperAssistantService()
    ServiceManager.register_factory("developer_assistant_service", _make_developer_assistant)

    def _make_self_development():
        from backend.services.self_development_service import SelfDevelopmentService
        return SelfDevelopmentService()
    ServiceManager.register_factory("self_development_service", _make_self_development)

    def _make_research_service():
        from backend.services.research_agent import ResearchAgentService
        return ResearchAgentService()
    ServiceManager.register_factory("research_service", _make_research_service)

    def _make_voice_intelligence():
        from backend.services.voice_intelligence import VoiceIntelligenceService
        return VoiceIntelligenceService()
    ServiceManager.register_factory("voice_intelligence_service", _make_voice_intelligence)

    def _make_productivity_service():
        from backend.services.productivity_service import ProductivityService
        return ProductivityService()
    ServiceManager.register_factory("productivity_service", _make_productivity_service)

    def _make_workspace_intel():
        from backend.services.workspace_intelligence import WorkspaceIntelligenceService
        return WorkspaceIntelligenceService()
    ServiceManager.register_factory("workspace_intelligence", _make_workspace_intel)

    # 9. Mobile Gateway & Bridge Subsystems
    def _make_file_indexer():
        from backend.services.file_indexer import FileIndexerService
        return FileIndexerService()
    ServiceManager.register_factory("file_indexer", _make_file_indexer)

    def _make_mobile_bridge():
        from backend.services.mobile_bridge import MobileBridgeService
        return MobileBridgeService()
    ServiceManager.register_factory("mobile_bridge", _make_mobile_bridge)

    def _make_mobile_auth():
        from backend.services.mobile_auth import MobileAuthService
        return MobileAuthService()
    ServiceManager.register_factory("mobile_auth_service", _make_mobile_auth)

    def _make_mobile_gateway():
        from backend.services.mobile_gateway import MobileGatewayService
        return MobileGatewayService()
    ServiceManager.register_factory("mobile_gateway_service", _make_mobile_gateway)

    def _make_oauth_service():
        from backend.services.oauth_service import oauth_service
        return oauth_service
    ServiceManager.register_factory("oauth_service", _make_oauth_service)

    def _make_bt_proximity():
        from backend.services.bluetooth_proximity import bluetooth_proximity_service
        return bluetooth_proximity_service
    ServiceManager.register_factory("bluetooth_proximity_service", _make_bt_proximity)

    # 10. Self-Improving Engines & Strategy Memory
    def _make_experience_engine():
        from backend.services.experience_engine import ExperienceEngineService
        return ExperienceEngineService()
    ServiceManager.register_factory("experience_engine", _make_experience_engine)

    def _make_reflection_engine():
        from backend.services.reflection_engine import ReflectionEngineService
        return ReflectionEngineService()
    ServiceManager.register_factory("reflection_engine", _make_reflection_engine)

    def _make_self_healing():
        from backend.services.self_healing import SelfHealingEngine
        return SelfHealingEngine()
    ServiceManager.register_factory("self_healing", _make_self_healing)

    def _make_strategy_memory():
        from backend.services.strategy_memory import StrategyMemoryService
        return StrategyMemoryService()
    ServiceManager.register_factory("strategy_memory", _make_strategy_memory)

    def _make_skill_library():
        from backend.services.skills.skill_library import SkillLibraryService
        return SkillLibraryService()
    ServiceManager.register_factory("skill_library", _make_skill_library)

    def _make_live_mode():
        from backend.services.live_mode.live_engine import LiveModeEngine
        return LiveModeEngine()
    ServiceManager.register_factory("live_mode_engine", _make_live_mode)

    # 11. Memory & RAG Subsystems
    def _make_memory_service():
        from backend.services.memory import MemoryService
        return MemoryService()
    ServiceManager.register_factory("memory_service", _make_memory_service)

    def _make_rag_service():
        from backend.services.rag_service import RAGService
        mem = ServiceManager.get_instance("memory_service")
        chroma_client = getattr(mem, "_chroma_client", None) if mem else None
        return RAGService(chroma_client=chroma_client)
    ServiceManager.register_factory("rag_service", _make_rag_service)

    # 12. MCP Client Manager
    def _make_mcp():
        from backend.mcp.client import MCPClientManager
        return MCPClientManager()
    ServiceManager.register_factory("mcp_client_manager", _make_mcp)

    # 13. Orchestration & Domain Agents
    def _make_general_agent():
        from backend.agents.domain.general_agent import GeneralAgent
        return GeneralAgent()
    ServiceManager.register_factory("general_agent", _make_general_agent)

    def _make_research_agent():
        from backend.agents.domain.research_agent import ResearchAgent
        return ResearchAgent()
    ServiceManager.register_factory("research_agent_domain", _make_research_agent)

    def _make_developer_agent():
        from backend.agents.domain.developer_agent import DeveloperAgent
        return DeveloperAgent()
    ServiceManager.register_factory("developer_agent_domain", _make_developer_agent)

    def _make_automation_agent():
        from backend.agents.domain.automation_agent import AutomationAgent
        return AutomationAgent()
    ServiceManager.register_factory("automation_agent_domain", _make_automation_agent)

    def _make_planner():
        from backend.agents.planner import PlannerAgent
        return PlannerAgent(
            llm_service=ServiceManager.get_instance("llm_service"),
            automation_service=ServiceManager.get_instance("automation_service"),
            screen_service=ServiceManager.get_instance("screen_service"),
            browser_service=ServiceManager.get_instance("browser_service"),
            memory_service=ServiceManager.get_instance("memory_service"),
            safety_service=ServiceManager.get_instance("safety_service"),
            vision_service=ServiceManager.get_instance("vision_service"),
            desktop_automation_service=ServiceManager.get_instance("desktop_automation_service"),
            developer_assistant_service=ServiceManager.get_instance("developer_assistant_service"),
            research_service=ServiceManager.get_instance("research_service"),
            voice_intelligence_service=ServiceManager.get_instance("voice_intelligence_service"),
            productivity_service=ServiceManager.get_instance("productivity_service"),
        )
    ServiceManager.register_factory("planner_agent", _make_planner)

    def _make_voice_agent():
        from backend.services.voice import VoiceManager
        return VoiceManager(
            wake_word_service=ServiceManager.get_instance("wake_word_service"),
            stt_service=ServiceManager.get_instance("stt_service"),
            tts_service=ServiceManager.get_instance("tts_service"),
            planner_agent=ServiceManager.get_instance("planner_agent"),
            audio_device_manager=ServiceManager.get_instance("audio_device_manager"),
            voice_intelligence_service=ServiceManager.get_instance("voice_intelligence_service"),
        )
    ServiceManager.register_factory("voice_agent", _make_voice_agent)
    ServiceManager.register_factory("voice_manager", _make_voice_agent)

    logger.info(f"✓ Registered {len(ServiceManager.list_registered_factories())} optional/heavy services for lazy loading")
