"""
Multimodal vision analysis implementation for screen understanding.
"""
import asyncio
import json
from typing import Any, Optional
from backend.utils.logger import logger
from backend.services.llm.prompts import extract_clean_user_request


async def vision_analysis_impl(
    service: Any,
    image_base64: str,
    prompt: str = "Describe what you see on the screen and identify key UI elements.",
) -> str:
        """
        Analyse an image using Gemini Vision, falling back to OpenAI GPT-4o Vision.
        Note: Ollama text-only models are skipped — vision always uses cloud providers.
        """
        # Always try Gemini for vision (regardless of primary_provider)
        # since Ollama local models don't support image input
        use_gemini = service.gemini_available

        if use_gemini:
            try:
                import base64
                from google.genai import types
                image_bytes = base64.b64decode(image_base64)

                try:
                    response = await service.gemini_client.aio.models.generate_content(
                        model=service.gemini_model_name,
                        contents=[
                            question,
                            types.Part.from_bytes(
                                data=image_bytes,
                                mime_type="image/png"
                            )
                        ],
                        config=types.GenerateContentConfig(
                            max_output_tokens=max_tokens,
                            system_instruction="You are JARVIS, analysing the user's screen. Describe what you see concisely and answer the user's question."
                        )
                    )
                except Exception as e:
                    if self._rotate_gemini_key():
                        response = await service.gemini_client.aio.models.generate_content(
                            model=service.gemini_model_name,
                            contents=[
                                question,
                                types.Part.from_bytes(
                                    data=image_bytes,
                                    mime_type="image/png"
                                )
                            ],
                            config=types.GenerateContentConfig(
                                max_output_tokens=max_tokens,
                                system_instruction="You are JARVIS, analysing the user's screen. Describe what you see concisely and answer the user's question."
                            )
                        )
                    else:
                        raise e
                self.total_requests += 1
                return response.text or ""
            except Exception as e:
                logger.error("Gemini vision analysis failed: {}. Falling back to OpenAI...", e)

        # OpenAI Fallback
        if not service.openai_client:
            return "I'm unable to analyse the screen, sir, as no fallback provider is available."

        messages = [
            {
                "role": "system",
                "content": "You are JARVIS, analysing the user's screen. Describe what you see concisely and answer the user's question."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        try:
            response = await service.openai_client.chat.completions.create(
                model=service.openai_model_name,
                messages=messages,
                max_tokens=max_tokens,
            )
            self.total_requests += 1
            if response.usage:
                service.total_prompt_tokens += response.usage.prompt_tokens
                service.total_completion_tokens += response.usage.completion_tokens

            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI vision fallback failed: {}", e)
            return f"I'm unable to analyse the screen at the moment, sir: {e}"

