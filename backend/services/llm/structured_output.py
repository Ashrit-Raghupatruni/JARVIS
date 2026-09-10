"""
Structured output generation and simple prompt pipeline completions.
"""
import asyncio
import json
import time
from typing import Any, Optional
from backend.utils.logger import logger
from backend.services.llm.prompts import extract_clean_user_request


async def simple_completion_impl(
    service: Any,
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> str:
        """
        Non-streaming single-turn completion without tools. Handles dynamic failover.
        """
        available_providers = await service.router.get_ranked_providers()
        
        last_error = None
        fallback_count = 0

        # ── Prash First-Try (simple completion) ──────────────────────
        # Only run Prash on user chat queries, not on internal agent planning/selection prompts
        is_agent_prompt = False
        prompt_and_system = (prompt or "") + " " + (system_prompt or "")
        prompt_lower = prompt_and_system.lower()
        
        agent_keywords = [
            "planner", "selector", "validator", "agent", 
            "compiler", "json", "transcript", "workflow", 
            "execution", "tool", "database", "system prompt"
        ]
        if any(kw in prompt_lower for kw in agent_keywords):
            is_agent_prompt = True

        if service.prash_enabled and service.prash_engine and not is_agent_prompt:
            start_time = time.time()
            try:
                if not service._prash_initialized:
                    init_ok = await service.prash_engine.init()
                    service._prash_initialized = init_ok

                if service._prash_initialized and service.prash_engine.is_available():
                    logger.info("Attempting Prash simple completion...")
                    try:
                        response_text, is_confident, metadata = await asyncio.wait_for(
                            service.prash_engine.generate(
                                prompt=prompt,
                                max_tokens=min(128, max_tokens),
                                temperature=temperature,
                            ),
                            timeout=4.0
                        )
                    except (asyncio.TimeoutError, TimeoutError):
                        logger.warning("PrashEngine simple completion exceeded 4.0s. Falling back.")
                        response_text, is_confident, metadata = "", False, {"entropy": 999.0}
                    prash_entropy = metadata.get("entropy", 999.0)
                    prash_confident = is_confident and len(response_text.strip()) > 5

                    latency = time.time() - start_time

                    if prash_confident:
                        logger.info(f"✓ Prash simple completion confident (entropy={prash_entropy:.2f})")
                        service.total_requests += 1
                        await service.router.record_metric(
                            provider="prash", model="prash-local-v0.1",
                            latency=latency, throughput=metadata.get("tokens_generated", 0) / max(0.01, latency),
                            cost=0.0, success=True
                        )
                        await service.router.record_decision(
                            selected_provider="prash", selected_model="prash-local-v0.1",
                            latency=latency, success=True, fallback_count=0,
                            prompt_tokens=0, completion_tokens=metadata.get("tokens_generated", 0), cost=0.0
                        )
                        return response_text
                    else:
                        logger.info(f"Prash simple completion low confidence (entropy={prash_entropy:.2f}). Falling back.")
                        fallback_count += 1
                        await service.router.record_metric(
                            provider="prash", model="prash-local-v0.1",
                            latency=latency, throughput=0.0, cost=0.0, success=False,
                            error_msg=f"Low confidence (entropy={prash_entropy:.2f})"
                        )
            except Exception as e:
                logger.warning(f"Prash simple completion error: {e}. Falling back.")
                fallback_count += 1

        # ── Cloud Provider Cascade ───────────────────────────────────
        
        for i, provider in enumerate(available_providers):
            start_time = time.time()
            prompt_tokens_start = service.total_prompt_tokens
            completion_tokens_start = service.total_completion_tokens
            success = False
            error_msg = None
            model_name = service.router._get_model_name(provider)
            
            try:
                logger.info(f"Attempting simple completion with: {provider}")
                if i > 0:
                    fallback_count += 1
                    
                messages = [
                    {"role": "system", "content": system_prompt or self.get_system_prompt()},
                    {"role": "user", "content": prompt},
                ]

                # Wrap the API call in a 30s timeout
                if provider == "ollama":
                    try:
                        resp = await asyncio.wait_for(
                            service.ollama_client.chat.completions.create(
                                model=service.ollama_model_name,
                                messages=messages,
                                max_tokens=max_tokens,
                                temperature=temperature,
                            ),
                            timeout=28.0
                        )
                    except Exception as e:
                        if service._rotate_ollama_model():
                            resp = await asyncio.wait_for(
                                service.ollama_client.chat.completions.create(
                                    model=service.ollama_model_name,
                                    messages=messages,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                ),
                                timeout=28.0
                            )
                        else:
                            raise e
                    service.total_requests += 1
                    if resp.usage:
                        service.total_prompt_tokens += resp.usage.prompt_tokens
                        service.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""

                elif provider == "gemini":
                    from google.genai import types
                    try:
                        resp = await asyncio.wait_for(
                            service.gemini_client.aio.models.generate_content(
                                model=service.gemini_model_name,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    temperature=temperature,
                                    max_output_tokens=max_tokens,
                                    system_instruction=system_prompt or self.get_system_prompt()
                                )
                            ),
                            timeout=15.0
                        )
                    except Exception as e:
                        if service._rotate_gemini_key():
                            resp = await asyncio.wait_for(
                                service.gemini_client.aio.models.generate_content(
                                    model=service.gemini_model_name,
                                    contents=prompt,
                                    config=types.GenerateContentConfig(
                                        temperature=temperature,
                                        max_output_tokens=max_tokens,
                                        system_instruction=system_prompt or self.get_system_prompt()
                                    )
                                ),
                                timeout=15.0
                            )
                        else:
                            raise e
                    service.total_requests += 1
                    content = resp.text or ""

                elif provider == "groq":
                    resp = await asyncio.wait_for(
                        service.groq_client.chat.completions.create(
                            model=service.groq_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    service.total_requests += 1
                    if resp.usage:
                        service.total_prompt_tokens += resp.usage.prompt_tokens
                        service.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""

                elif provider == "openrouter":
                    resp = await asyncio.wait_for(
                        service.openrouter_client.chat.completions.create(
                            model=service.openrouter_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    service.total_requests += 1
                    if resp.usage:
                        service.total_prompt_tokens += resp.usage.prompt_tokens
                        service.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""

                elif provider == "openai":
                    resp = await asyncio.wait_for(
                        service.openai_client.chat.completions.create(
                            model=service.openai_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    service.total_requests += 1
                    if resp.usage:
                        service.total_prompt_tokens += resp.usage.prompt_tokens
                        service.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""
                    
                elif provider == "nvidia":
                    resp = await asyncio.wait_for(
                        service.nvidia_client.chat.completions.create(
                            model=service.nvidia_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    service.total_requests += 1
                    if resp.usage:
                        service.total_prompt_tokens += resp.usage.prompt_tokens
                        service.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""
                else:
                    continue

                # Succeeded! Record decision and return
                latency = time.time() - start_time
                prompt_diff = service.total_prompt_tokens - prompt_tokens_start
                comp_diff = service.total_completion_tokens - completion_tokens_start
                cost = (comp_diff / 1000000) * service.router.costs.get(provider, 0.0)

                await service.router.record_metric(
                    provider=provider,
                    model=model_name,
                    latency=latency,
                    throughput=comp_diff / max(0.01, latency),
                    cost=cost,
                    success=True
                )

                await service.router.record_decision(
                    selected_provider=provider,
                    selected_model=model_name,
                    latency=latency,
                    success=True,
                    fallback_count=fallback_count,
                    prompt_tokens=prompt_diff,
                    completion_tokens=comp_diff,
                    cost=cost
                )
                return content

            except Exception as e:
                logger.error(f"Simple completion failed with {provider}: {e}")
                last_error = e
                error_msg = str(e)
                latency = time.time() - start_time
                
                await service.router.record_metric(
                    provider=provider,
                    model=model_name,
                    latency=latency,
                    throughput=0.0,
                    cost=0.0,
                    success=False,
                    error_msg=error_msg
                )

        return "I apologize, sir, but I am currently having trouble reaching all my primary and fallback AI services. Please check your internet connection or verify your API configuration."

