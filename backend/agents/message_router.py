"""
JARVIS AI OS - Code-Level Intent & Message Router.
=================================================
Classifies incoming user messages into strict architectural execution routes:
1. ACTION_REQUEST: ("run AP24110011746", "open Chrome", "find my resume") -> Planner -> Tool Registry -> Execution
2. LIVE_MODE_REQUEST: ("what's on my screen?", "click that button") -> World Model -> Live Mode -> Planner -> Execution
3. WORKFLOW_REQUEST: ("run n8n workflow", "create workflow") -> n8n Service -> Workflow Engine
4. RESEARCH_REQUEST: ("search web for latest news", "read http...") -> Research Agent
5. SYSTEM_REQUEST: ("shutdown", "lock screen", "set volume") -> System Service
6. KNOWLEDGE_REQUEST: ("what is binary search?") -> Direct Reasoning
"""

import re
from enum import Enum
from typing import Dict, Any
from loguru import logger


class RequestCategory(str, Enum):
    ACTION_REQUEST = "action_request"
    LIVE_MODE_REQUEST = "live_mode_request"
    WORKFLOW_REQUEST = "workflow_request"
    RESEARCH_REQUEST = "research_request"
    SYSTEM_REQUEST = "system_request"
    KNOWLEDGE_REQUEST = "knowledge_request"


def classify_request(user_message: str) -> RequestCategory:
    """
    Code-level deterministic request classifier.
    Ensures action, workflow, research, system, and live mode requests are intercepted
    before reaching direct LLM text calls.
    """
    msg_lower = user_message.lower().strip()

    # 1. Live Mode / Screen-Aware Perception & UI Interaction Triggers
    live_mode_keywords = [
        "what am i seeing", "what's on my screen", "what is on my screen",
        "read screen", "see screen", "click button", "click that", "click the", "click on",
        "tap ", "press button", "hit button", "select button", "fill form", "fill this form",
        "describe screen", "screen context", "what should i do next", "active window", "on screen"
    ]
    if any(kw in msg_lower for kw in live_mode_keywords) or msg_lower.startswith(("click", "tap", "fill", "press button")):
        logger.info("⚡ MessageRouter classified: LIVE_MODE_REQUEST for prompt '{}'", user_message[:60])
        return RequestCategory.LIVE_MODE_REQUEST

    # 2. Workflow Automation Engine Triggers
    if any(kw in msg_lower for kw in ["n8n", "workflow", "canvas", "trigger workflow", "run workflow"]):
        logger.info("⚡ MessageRouter classified: WORKFLOW_REQUEST for prompt '{}'", user_message[:60])
        return RequestCategory.WORKFLOW_REQUEST

    # 3. Online Research & Search Triggers
    if any(kw in msg_lower for kw in ["search online", "search web", "google", "find online", "http://", "https://"]):
        logger.info("⚡ MessageRouter classified: RESEARCH_REQUEST for prompt '{}'", user_message[:60])
        return RequestCategory.RESEARCH_REQUEST

    # 4. System Control Triggers
    if any(kw in msg_lower for kw in ["shutdown", "restart", "lock screen", "set volume", "mute", "unmute"]):
        logger.info("⚡ MessageRouter classified: SYSTEM_REQUEST for prompt '{}'", user_message[:60])
        return RequestCategory.SYSTEM_REQUEST

    # 5. Action / Desktop OS / Script / Job ID Execution Triggers
    action_keywords = [
        "open ", "launch ", "run ", "execute ", "find ", "search file", "locate ",
        "delete ", "clean ", "clear ", "play ", "pause ", "close ", "kill ",
        "type ", "press ", "move ", "copy ", "rename ", "spotify", "youtube",
        "chrome", "notepad", "calculator", "python", ".py", ".exe", ".pdf", "script"
    ]
    is_action_start = msg_lower.startswith(("open", "run", "play", "find", "delete", "clean", "execute", "launch", "search", "start"))
    has_job_id = bool(re.search(r"\b[A-Z]{2,}\d{5,}\b", user_message))

    if any(kw in msg_lower for kw in action_keywords) or is_action_start or has_job_id:
        logger.info("⚡ MessageRouter classified: ACTION_REQUEST for prompt '{}'", user_message[:60])
        return RequestCategory.ACTION_REQUEST

    # 6. Knowledge / Conversational Reasoning Triggers
    logger.info("⚡ MessageRouter classified: KNOWLEDGE_REQUEST for prompt '{}'", user_message[:60])
    return RequestCategory.KNOWLEDGE_REQUEST
