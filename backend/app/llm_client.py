"""LLM client — Groq (primary) + OpenRouter (fallback).

All LLM calls go through this module. Each provider gets 3 retries
with exponential backoff (1s, 2s, 4s). If primary exhausts retries,
we fall through to the fallback provider.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx
import structlog
from groq import AsyncGroq

from app.config import get_settings
from app.prompt_builder import PromptResult

logger = structlog.get_logger(__name__)


class LLMUnavailableError(Exception):
    """Raised when all LLM providers have failed."""


@dataclass(frozen=True)
class LLMResponse:
    """Response from an LLM call."""

    text: str
    model_used: str
    provider: str
    tokens_used: int
    latency_ms: float


async def generate(
    prompt: PromptResult,
    *,
    clone_id: str,
    session_id: str = "unknown",
) -> LLMResponse:
    """Generate a response using Groq (primary) with OpenRouter fallback.

    Raises:
        LLMUnavailableError: If both providers fail after all retries.
    """
    import yaml
    settings = get_settings()
    config_path = settings.get_clone_config_path(clone_id)
    requested_model = ""
    if config_path.exists():
        try:
            config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if "model" in config_data:
                requested_model = str(config_data["model"])
        except Exception:
            pass

    # Skip Groq if the model is an OpenRouter-specific model (contains '/')
    if requested_model and "/" in requested_model:
        try:
            return await _call_openrouter(prompt, clone_id=clone_id, session_id=session_id)
        except Exception as exc:
            logger.error(
                "all_llm_providers_failed",
                clone_id=clone_id,
                session_id=session_id,
                error=str(exc),
            )
            raise LLMUnavailableError(
                "OpenRouter failed after retries."
            ) from exc

    try:
        return await _call_groq(prompt, clone_id=clone_id, session_id=session_id)
    except Exception as exc:
        logger.warning(
            "groq_exhausted_falling_back",
            clone_id=clone_id,
            session_id=session_id,
            error=str(exc),
        )

    try:
        return await _call_openrouter(prompt, clone_id=clone_id, session_id=session_id)
    except Exception as exc:
        logger.error(
            "all_llm_providers_failed",
            clone_id=clone_id,
            session_id=session_id,
            error=str(exc),
        )
        raise LLMUnavailableError(
            "All LLM providers (Groq, OpenRouter) failed after retries."
        ) from exc


async def _call_groq(
    prompt: PromptResult, *, clone_id: str, session_id: str,
) -> LLMResponse:
    """Call Groq API with 3-retry exponential backoff."""
    import yaml
    settings = get_settings()
    
    # Load overrides from config.yaml
    temperature = settings.llm_temperature
    max_tokens = settings.max_output_tokens
    groq_model = settings.groq_model
    config_path = settings.get_clone_config_path(clone_id)
    if config_path.exists():
        try:
            config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if "temperature" in config_data:
                temperature = float(config_data["temperature"])
            if "max_output_tokens" in config_data:
                max_tokens = int(config_data["max_output_tokens"])
            if "model" in config_data:
                groq_model = str(config_data["model"])
        except Exception:
            pass

    client = AsyncGroq(api_key=settings.groq_api_key)
    last_error: Exception | None = None

    try:
        for attempt in range(settings.max_retries):
            try:
                messages = [
                    {"role": "system", "content": prompt.system_prompt.strip()},
                    {"role": "user", "content": prompt.user_prompt}
                ]

                import json as _json
                print("=== LLM PAYLOAD DEBUG ===")
                print(_json.dumps(messages, indent=2, ensure_ascii=False)[:3000])
                print("=========================")

                start_time = time.monotonic()
                response = await client.chat.completions.create(
                    model=groq_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    frequency_penalty=0.6,
                    presence_penalty=0.4,
                )
                elapsed_ms = (time.monotonic() - start_time) * 1000
                text = response.choices[0].message.content or ""
                tokens = response.usage.total_tokens if response.usage else 0

                logger.info(
                    "groq_success", clone_id=clone_id, session_id=session_id,
                    model=groq_model, tokens=tokens,
                    latency_ms=round(elapsed_ms, 1), attempt=attempt + 1,
                )
                return LLMResponse(
                    text=text, model_used=groq_model, provider="groq",
                    tokens_used=tokens, latency_ms=round(elapsed_ms, 1),
                )
            except Exception as exc:
                last_error = exc
                if attempt < settings.max_retries - 1:
                    delay = settings.retry_delays[attempt]
                    logger.warning(
                        "groq_retry", clone_id=clone_id, session_id=session_id,
                        attempt=attempt + 1, delay_seconds=delay, error=str(exc),
                    )
                    await asyncio.sleep(delay)
    finally:
        await client.close()

    raise RuntimeError(f"Groq failed after {settings.max_retries} attempts: {last_error}")


async def _call_openrouter(
    prompt: PromptResult, *, clone_id: str, session_id: str,
) -> LLMResponse:
    """Call OpenRouter API with 3-retry exponential backoff."""
    import yaml
    settings = get_settings()
    last_error: Exception | None = None
    
    # Load overrides from config.yaml
    temperature = settings.llm_temperature
    max_tokens = settings.max_output_tokens
    openrouter_model = settings.openrouter_model
    config_path = settings.get_clone_config_path(clone_id)
    if config_path.exists():
        try:
            config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if "temperature" in config_data:
                temperature = float(config_data["temperature"])
            if "max_output_tokens" in config_data:
                max_tokens = int(config_data["max_output_tokens"])
            if "model" in config_data:
                openrouter_model = str(config_data["model"])
        except Exception:
            pass

    for attempt in range(settings.max_retries):
        try:
            start_time = time.monotonic()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/abdulmueezdev/AI-Bot",
                        "X-Title": "Digital Clone AI",
                    },
                    json={
                        "model": openrouter_model,
                        "messages": [
                            {"role": "system", "content": prompt.system_prompt},
                            {"role": "user", "content": prompt.user_prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
            elapsed_ms = (time.monotonic() - start_time) * 1000

            if response.status_code != 200:
                raise RuntimeError(f"OpenRouter HTTP {response.status_code}: {response.text}")

            data = response.json()
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)

            logger.info(
                "openrouter_success", clone_id=clone_id, session_id=session_id,
                model=openrouter_model, tokens=tokens,
                latency_ms=round(elapsed_ms, 1), attempt=attempt + 1,
            )
            return LLMResponse(
                text=text, model_used=openrouter_model, provider="openrouter",
                tokens_used=tokens, latency_ms=round(elapsed_ms, 1),
            )
        except Exception as exc:
            last_error = exc
            if attempt < settings.max_retries - 1:
                delay = settings.retry_delays[attempt]
                logger.warning(
                    "openrouter_retry", clone_id=clone_id, session_id=session_id,
                    attempt=attempt + 1, delay_seconds=delay, error=str(exc),
                )
                await asyncio.sleep(delay)

    raise RuntimeError(f"OpenRouter failed after {settings.max_retries} attempts: {last_error}")
