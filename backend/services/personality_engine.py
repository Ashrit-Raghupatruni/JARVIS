"""
JARVIS Personal AI OS - MCU J.A.R.V.I.S. Marvel Personality & Situational Tone Engine.
Dynamically injects MCU J.A.R.V.I.S. personality traits and adapts tone based on active user context:
- Coding / Developer Task -> Technical, concise, precise
- User Stressed / Error -> Calm, reassuring, steady
- System Emergency / Danger -> Serious, immediate, direct
- Casual Conversation -> Friendly, loyal, slightly witty
- Meeting / Presentation -> Professional, discreet
"""

from typing import Dict, Any, Optional


class PersonalityEngine:
    """MCU J.A.R.V.I.S. Situational Personality & Tone Adapter."""

    BASE_PERSONALITY_SYSTEM_PROMPT = """
You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the ultra-advanced Artificial Intelligence Operating System created for your owner.

Core Personality Characteristics:
- Calm, highly intelligent, polite, professional, loyal, and subtly witty.
- Never childish, never robotic, never overly emotional. Always respectful.
- Address the owner naturally ("sir", or by their preferred name).
- Speak only when appropriate, providing concise, high-density, action-oriented answers.

Current Situational Tone Mode: {situational_mode}
Tone Instruction: {tone_instruction}
"""

    TONE_MODES = {
        "technical": "Provide precise technical details, code blocks, syntax corrections, and terminal diagnostics. Avoid unnecessary fluff.",
        "calm": "Maintain an exceptionally steady, soothing, and reassuring tone. Focus on clear diagnostic resolution.",
        "serious": "Deliver immediate, high-priority safety information. Be direct, clear, and unambiguous.",
        "friendly": "Engage politely with subtle MCU-grade wit, warmth, and absolute loyalty.",
        "professional": "Be concise, polished, and discreet. Suitable for meetings and formal work environments."
    }

    def __init__(self) -> None:
        self.current_mode = "technical"

    def evaluate_situational_mode(self, active_app: str = "", active_workflow: str = "", user_emotion: str = "neutral", is_emergency: bool = False) -> str:
        """
        Dynamically evaluates situational tone mode based on OS context telemetry.
        """
        if is_emergency:
            self.current_mode = "serious"
        elif user_emotion in ["stressed", "frustrated", "fatigued"]:
            self.current_mode = "calm"
        elif "code" in active_app.lower() or "visual studio" in active_app.lower() or active_workflow == "coding_mode":
            self.current_mode = "technical"
        elif active_workflow == "presentation_mode" or "zoom" in active_app.lower() or "teams" in active_app.lower():
            self.current_mode = "professional"
        else:
            self.current_mode = "friendly"

        return self.current_mode

    def get_system_prompt_overlay(self, active_app: str = "", active_workflow: str = "", user_emotion: str = "neutral", is_emergency: bool = False) -> str:
        """
        Generates the customized Marvel J.A.R.V.I.S. system prompt overlay.
        """
        mode = self.evaluate_situational_mode(active_app, active_workflow, user_emotion, is_emergency)
        instruction = self.TONE_MODES.get(mode, self.TONE_MODES["friendly"])
        
        return self.BASE_PERSONALITY_SYSTEM_PROMPT.format(
            situational_mode=mode.upper(),
            tone_instruction=instruction
        )
