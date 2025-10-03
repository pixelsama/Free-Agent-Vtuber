from __future__ import annotations

"""LLM streaming client wrappers for dialog-engine."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from .settings import LLMSettings, OpenAISettings, settings

logger = logging.getLogger(__name__)

ChatMessage = Dict[str, Any]


class LLMNotConfiguredError(RuntimeError):
    """Raised when trying to use the LLM client without runtime configuration."""


class LLMStreamEmptyError(RuntimeError):
    """Raised when an LLM stream finishes without emitting any text tokens."""

    def __init__(self, message: str, *, tool_calls: Optional[list[Any]] = None) -> None:
        super().__init__(message)
        self.tool_calls = tool_calls or []


class OpenAIChatClient:
    """Thin wrapper around AsyncOpenAI with retry-aware streaming."""

    def __init__(
        self,
        openai_cfg: Optional[OpenAISettings] = None,
        llm_cfg: Optional[LLMSettings] = None,
        *,
        client: Optional[AsyncOpenAI] = None,
    ) -> None:
        self._openai_cfg = openai_cfg or settings.openai
        self._llm_cfg = llm_cfg or settings.llm
        api_key = self._openai_cfg.api_key
        if client is None:
            if not api_key:
                raise LLMNotConfiguredError("OPENAI_API_KEY is required for real LLM usage")
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self._openai_cfg.base_url,
                organization=self._openai_cfg.organization,
            )
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion deltas with retry and logging."""

        cfg = self._llm_cfg
        params: Dict[str, Any] = {
            "model": model or cfg.model,
            "messages": list(messages),
            "temperature": temperature if temperature is not None else cfg.temperature,
            "max_tokens": max_tokens if max_tokens is not None else cfg.max_tokens,
            "top_p": top_p if top_p is not None else cfg.top_p,
            "frequency_penalty": cfg.frequency_penalty,
            "presence_penalty": cfg.presence_penalty,
            "stream": True,
            "timeout": timeout if timeout is not None else cfg.timeout,
        }
        if extra_options:
            params.update(extra_options)

        attempt = 0
        last_error: Exception | None = None
        total_attempts = cfg.retry_limit + 1
        while attempt < total_attempts:
            attempt += 1
            stream = None
            try:
                stream = await self._client.chat.completions.create(**params)
                logger.info(
                    "llm.stream.start",
                    extra={
                        "model": params["model"],
                        "temperature": params.get("temperature"),
                        "attempt": attempt,
                        "max_tokens": params.get("max_tokens"),
                    },
                )
                has_content = False
                collected_tool_calls: list[Any] = []
                async for chunk in stream:
                    for choice in chunk.choices:
                        delta = choice.delta
                        if delta is None:
                            continue
                        text_delta = getattr(delta, "content", None)
                        if text_delta:
                            has_content = True
                            yield text_delta
                        tool_calls = getattr(delta, "tool_calls", None)
                        if tool_calls:
                            collected_tool_calls.extend(tool_calls)
                if not has_content:
                    logger.warning(
                        "llm.stream.empty",
                        extra={
                            "model": params.get("model"),
                            "tool_calls": collected_tool_calls,
                            "attempt": attempt,
                        },
                    )
                    raise LLMStreamEmptyError(
                        "LLM stream produced no text delta",
                        tool_calls=collected_tool_calls,
                    )
                logger.info(
                    "llm.stream.complete",
                    extra={"model": params["model"], "attempt": attempt},
                )
                return
            except Exception as exc:  # pragma: no cover - defensive catch
                last_error = exc
                logger.warning(
                    "llm.stream.error",
                    extra={"attempt": attempt, "model": params.get("model"), "error": repr(exc)},
                )
                if attempt >= total_attempts:
                    break
                await asyncio.sleep(cfg.retry_backoff_seconds * attempt)
            finally:
                if stream is not None:
                    try:
                        await stream.aclose()
                    except Exception:  # pragma: no cover - best effort cleanup
                        logger.debug("llm.stream.close_failed", exc_info=True)

        raise RuntimeError("LLM streaming failed after retries") from last_error

    async def generate_vision_reply(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Issue a non-streaming chat completion for multimodal prompts."""

        cfg = self._llm_cfg
        params: Dict[str, Any] = {
            "model": model or cfg.model,
            "messages": list(messages),
            "temperature": temperature if temperature is not None else cfg.temperature,
            "max_tokens": max_tokens if max_tokens is not None else cfg.max_tokens,
            "top_p": top_p if top_p is not None else cfg.top_p,
            "frequency_penalty": cfg.frequency_penalty,
            "presence_penalty": cfg.presence_penalty,
            "timeout": timeout if timeout is not None else cfg.timeout,
        }
        if extra_options:
            params.update(extra_options)

        attempt = 0
        last_error: Exception | None = None
        total_attempts = cfg.retry_limit + 1

        while attempt < total_attempts:
            attempt += 1
            try:
                resp = await self._client.chat.completions.create(**params)
                logger.info(
                    "llm.vision.complete",
                    extra={
                        "model": params.get("model"),
                        "attempt": attempt,
                        "max_tokens": params.get("max_tokens"),
                    },
                )
                choices = getattr(resp, "choices", [])
                for choice in choices:
                    message = getattr(choice, "message", None)
                    if not message:
                        continue
                    content = getattr(message, "content", None)
                    if isinstance(content, str) and content.strip():
                        return content
                logger.warning(
                    "llm.vision.empty",
                    extra={"model": params.get("model"), "attempt": attempt},
                )
                raise RuntimeError("vision_no_content")
            except Exception as exc:  # pragma: no cover - defensive catch
                last_error = exc
                logger.warning(
                    "llm.vision.error",
                    extra={"attempt": attempt, "model": params.get("model"), "error": repr(exc)},
                )
                if attempt >= total_attempts:
                    break
                await asyncio.sleep(cfg.retry_backoff_seconds * attempt)

        raise RuntimeError("LLM vision completion failed after retries") from last_error


__all__ = ["OpenAIChatClient", "LLMNotConfiguredError", "LLMStreamEmptyError", "ChatMessage"]
