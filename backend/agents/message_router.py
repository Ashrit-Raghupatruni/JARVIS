"""
JARVIS AI OS - Code-Level Intent & Message Router.

Classifies incoming user messages into 3 strict architectural execution routes:
1. ACTION_REQUEST: ("run this", "open Chrome", "find my resume") -> Planner -> Tool Registry -> Execution
2. LIVE_MODE_REQUEST: ("what's on my screen?", "click that button") -> World Model -> Live Mode -> Planner -> Execution/LLM
3. KNOWLEDGE_REQUEST: ("what is binary search?") -> LLM direct reasoning
"""

from enum import Enum
from typing import Dict, Any
from loguru import logger


class RequestCategory(str, Enum):
    ACTION_REQUEST = "action_request"
    LIVE_MODE_REQUEST = "live_mode_request"
    KNOWLEDGE_REQUEST = "knowledge_request"


def classify_request(user_message: str) -> RequestCategory:
    """
    Code-level deterministic request classifier.
    Ensures action and live mode requests are intercepted before reaching direct LLM calls.
    """
    msg_lower = user_message.lower().strip()

    # 1. Live Mode / Screen-Aware Perception Triggers
    live_mode_keywords = [
        "what am i seeing", "what's on my screen", "what is on my screen",
        "read screen", "see screen", "click button", "click that", "click the",
        "fill form", "fill this form", "describe screen", "screen context",
        "what should i do next", "active window", "on screen"
    ]
    if any(kw in msg_lower for kw in live_mode_keywords):
        logger.info("⚡ MessageRouter classified: LIVE_MODE_REQUEST for prompt '{}'", user_message[:60])
        return RequestCategory.LIVE_MODE_REQUEST

    # 2. Action / Desktop OS Execution Triggers
    action_keywords = [
        "open ", "launch ", "run ", "execute ", "find ", "search file", "locate ",
        "delete ", "clean ", "clear ", "play ", "pause ", "close ", "kill ",
        "type ", "press ", "move ", "copy ", "rename ", "shutdown", "restart",
        "lock", "spotify", "youtube", "music", "chrome", "notepad", "calculator",
        "python", ".py", ".exe", ".pdf", "script"
    ]
    # Check exact action verbs or target file patterns
    if any(kw in msg_lower for kw in action_keywords) or msg_lower.startswith(("open", "run", "play", "find", "delete", "clean", "execute", "launch", "search")):
        logger.info("⚡ MessageRouter classified: ACTION_REQUEST for prompt '{}'", user_message[:60])
        return RequestCategory.ACTION_REQUEST

    # 3. Knowledge / General Conversational Reasoning Triggers
    logger.info("⚡ MessageRouter classified: KNOWLEDGE_REQUEST for prompt '{}'", user_message[:60])
    return RequestCategory.KNOWLEDGE_REQUEST
