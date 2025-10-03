from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any, Dict, List, Optional

from .llm_client import LLMNotConfiguredError, LLMStreamEmptyError, OpenAIChatClient
from .ltm_client import LTMInlineClient
from .memory_store import MemoryTurn, ShortTermMemoryStore
from .settings import Settings, settings as runtime_settings


class ChatService:
    """Chat streaming service with optional real LLM support."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        llm_client_factory: Optional[Callable[[], OpenAIChatClient]] = None,
        memory_store: Optional[ShortTermMemoryStore] = None,
        ltm_client: Optional[LTMInlineClient] = None,
    ) -> None:
        self._settings = settings or runtime_settings
        self._llm_client_factory = llm_client_factory
        self._llm_client: Optional[OpenAIChatClient] = None
        self._memory_store = memory_store
        self._ltm_client = ltm_client

        self.last_token_count: int = 0
        self.last_ttft_ms: Optional[float] = None
        self.last_source: str = "mock"
        self.last_error: Optional[str] = None

    async def stream_reply(
        self,
        session_id: str,
        user_text: str,
        meta: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a reply either via real LLM or mock fallback."""

        meta = meta or {}
        self._reset_metrics()

        context_turns: List[MemoryTurn] = []
        ltm_snippets: List[str] = []

        if self._settings.llm.enabled:
            context_turns = await self._fetch_short_term_context(session_id=session_id)
            ltm_snippets = await self._fetch_ltm_snippets(
                session_id=session_id,
                user_text=user_text,
                meta=meta,
            )
            self._log_context_info(len(context_turns), len(ltm_snippets))
            try:
                async for delta in self._emit_with_metrics(
                    self._stream_llm(
                        session_id=session_id,
                        user_text=user_text,
                        meta=meta,
                        context=context_turns,
                        ltm_snippets=ltm_snippets,
                    ),
                    source="llm",
                ):
                    yield delta
                return
            except LLMStreamEmptyError as exc:
                self.last_error = "llm_empty_stream"
                self._log_llm_fallback(reason=f"empty_stream:{exc.tool_calls}")
            except LLMNotConfiguredError as exc:
                self.last_error = "llm_not_configured"
                self._log_llm_fallback(reason=str(exc))
            except Exception as exc:  # pragma: no cover - defensive catch
                self.last_error = exc.__class__.__name__
                self._log_llm_fallback(reason=repr(exc))

        async for delta in self._emit_with_metrics(
            self._stream_mock(user_text=user_text, meta=meta),
            source="mock",
        ):
            yield delta

    async def describe_image(
        self,
        session_id: str,
        *,
        image_b64: str,
        prompt: str | None,
        mime_type: str | None,
        meta: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        meta = meta or {}
        raw_prompt = (prompt or "").strip()
        prompt_text = raw_prompt or "请描述这张图片。"
        lang = str(meta.get("lang") or "zh")

        self._reset_metrics()
        context_turns: List[MemoryTurn] = []
        ltm_snippets: List[str] = []

        if self._settings.llm.enabled:
            context_turns = await self._fetch_short_term_context(session_id=session_id)
            ltm_snippets = await self._fetch_ltm_snippets(
                session_id=session_id,
                user_text=prompt_text,
                meta=meta,
            )
            self._log_context_info(len(context_turns), len(ltm_snippets))
            try:
                reply_text = await self._generate_vision_reply(
                    session_id=session_id,
                    prompt_text=prompt_text,
                    image_b64=image_b64,
                    mime_type=mime_type or "image/png",
                    meta=meta,
                    context=context_turns,
                    ltm_snippets=ltm_snippets,
                )
                self.last_source = "llm"
                self.last_error = None
                self.last_ttft_ms = None
                self.last_token_count = self._estimate_tokens(reply_text)
                stats = {
                    "chat": {
                        "source": self.last_source,
                        "tokens": self.last_token_count,
                        "ttft_ms": self.last_ttft_ms,
                    }
                }
                return {"reply": reply_text, "prompt": prompt_text, "stats": stats}
            except LLMNotConfiguredError as exc:
                self.last_error = "llm_not_configured"
                self._log_llm_fallback(reason=str(exc))
            except Exception as exc:  # pragma: no cover - defensive catch
                self.last_error = exc.__class__.__name__
                self._log_llm_fallback(reason=repr(exc))

        reply_text = self._craft_image_reply(raw_prompt, lang)
        self.last_source = "mock"
        self.last_ttft_ms = None
        self.last_token_count = self._estimate_tokens(reply_text)
        stats = {
            "chat": {
                "source": self.last_source,
                "tokens": self.last_token_count,
                "ttft_ms": self.last_ttft_ms,
            }
        }
        return {"reply": reply_text, "prompt": prompt_text, "stats": stats}

    async def _stream_llm(
        self,
        *,
        session_id: str,
        user_text: str,
        meta: Dict[str, Any],
        context: List[MemoryTurn],
        ltm_snippets: List[str],
    ) -> AsyncGenerator[str, None]:
        client = await self._ensure_llm_client()
        messages = self._compose_messages(
            user_text=user_text,
            meta=meta,
            context=context,
            ltm_snippets=ltm_snippets,
        )
        extra_options: Dict[str, Any] = {
            "extra_headers": {"x-session-id": session_id},
        }
        async for delta in client.stream_chat(messages, extra_options=extra_options):
            yield delta

    async def _stream_mock(
        self,
        *,
        user_text: str,
        meta: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        base = self._craft_reply(user_text=user_text, lang=(meta.get("lang") or "zh"))
        for word in base.split():
            await asyncio.sleep(0.02 + random.random() * 0.03)
            yield word + (" " if not word.endswith("\n") else "")

    async def _generate_vision_reply(
        self,
        *,
        session_id: str,
        prompt_text: str,
        image_b64: str,
        mime_type: str,
        meta: Dict[str, Any],
        context: List[MemoryTurn],
        ltm_snippets: List[str],
    ) -> str:
        client = await self._ensure_llm_client()
        messages = self._compose_messages(
            user_text=prompt_text,
            meta=meta,
            context=context,
            ltm_snippets=ltm_snippets,
        )
        content: list[Dict[str, Any]] = []
        if prompt_text:
            content.append({"type": "text", "text": prompt_text})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_b64}",
                },
            }
        )
        if messages:
            messages[-1] = {"role": "user", "content": content}
        else:  # pragma: no cover - defensive path
            messages = [{"role": "user", "content": content}]
        extra_options: Dict[str, Any] = {
            "extra_headers": {"x-session-id": session_id},
        }
        return await client.generate_vision_reply(messages, extra_options=extra_options)

    async def remember_turn(self, session_id: str, *, role: str, content: str) -> None:
        if not content or not content.strip():
            return
        cfg = self._settings.short_term
        if not cfg.enabled:
            return
        store = self._ensure_memory_store()
        try:
            await store.append_turn(session_id=session_id, role=role, content=content.strip())
        except Exception as exc:  # pragma: no cover - best effort log
            self._log_context_warning("stm.append.error", exc)

    async def _emit_with_metrics(
        self,
        generator: AsyncGenerator[str, None],
        *,
        source: str,
    ) -> AsyncGenerator[str, None]:
        start = time.perf_counter()
        async for chunk in generator:
            if self.last_ttft_ms is None:
                self.last_ttft_ms = (time.perf_counter() - start) * 1000.0
                self.last_source = source
            self.last_token_count += self._estimate_tokens(chunk)
            yield chunk

    async def _ensure_llm_client(self) -> OpenAIChatClient:
        if self._llm_client is not None:
            return self._llm_client

        if self._llm_client_factory is not None:
            client = self._llm_client_factory()
        else:
            client = OpenAIChatClient()
        self._llm_client = client
        return client

    def _compose_messages(
        self,
        *,
        user_text: str,
        meta: Dict[str, Any],
        context: List[MemoryTurn],
        ltm_snippets: List[str],
    ) -> list[Dict[str, str]]:
        system_prompt = meta.get("system_prompt")
        messages: list[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": str(system_prompt)})

        for turn in context:
            role = turn.role if turn.role in {"user", "assistant", "system"} else "assistant"
            messages.append({"role": role, "content": turn.content})

        if ltm_snippets:
            messages.append({"role": "system", "content": self._format_ltm_snippets(ltm_snippets)})
        messages.append({"role": "user", "content": user_text})
        return messages

    def _estimate_tokens(self, chunk: str) -> int:
        return max(len(chunk.strip().split()), 1) if chunk.strip() else 0

    def _reset_metrics(self) -> None:
        self.last_token_count = 0
        self.last_ttft_ms = None
        self.last_source = "mock"
        self.last_error = None

    def _log_llm_fallback(self, *, reason: str) -> None:
        # Deliberately late import to avoid global logging setup requirements.
        from logging import getLogger

        logger = getLogger(__name__)
        logger.warning("chat.llm.fallback", extra={"reason": reason})

    async def _fetch_short_term_context(self, session_id: str) -> List[MemoryTurn]:
        cfg = self._settings.short_term
        if not cfg.enabled:
            return []
        store = self._ensure_memory_store()
        try:
            return await store.fetch_recent(session_id=session_id, limit=cfg.context_turns)
        except Exception as exc:  # pragma: no cover - best effort log
            self._log_context_warning("stm.fetch.error", exc)
            return []

    async def _fetch_ltm_snippets(
        self,
        *,
        session_id: str,
        user_text: str,
        meta: Dict[str, Any],
    ) -> List[str]:
        cfg = self._settings.ltm_inline
        if not cfg.enabled:
            return []
        client = self._ensure_ltm_client()
        if not client or not client.is_configured():
            return []
        try:
            return await client.retrieve(
                session_id=session_id,
                user_text=user_text,
                meta=meta,
                limit=cfg.max_snippets,
            )
        except Exception as exc:  # pragma: no cover - best effort log
            self._log_context_warning("ltm.fetch.error", exc)
            return []

    def _ensure_memory_store(self) -> ShortTermMemoryStore:
        if self._memory_store is None:
            cfg = self._settings.short_term
            self._memory_store = ShortTermMemoryStore(
                db_path=cfg.db_path,
                default_limit=cfg.context_turns,
            )
        return self._memory_store

    def _ensure_ltm_client(self) -> Optional[LTMInlineClient]:
        if self._ltm_client is None:
            cfg = self._settings.ltm_inline
            self._ltm_client = LTMInlineClient(
                base_url=cfg.base_url,
                retrieve_path=cfg.retrieve_path,
                timeout=cfg.timeout,
                max_snippets=cfg.max_snippets,
            )
        return self._ltm_client

    def _format_ltm_snippets(self, snippets: List[str]) -> str:
        numbered = [f"{idx + 1}. {snippet}" for idx, snippet in enumerate(snippets)]
        return "Relevant memories:\n" + "\n".join(numbered)

    def _log_context_warning(self, event: str, exc: Exception) -> None:
        from logging import getLogger

        logger = getLogger(__name__)
        logger.warning(event, extra={"error": repr(exc)})

    def _log_context_info(self, stm_turns: int, ltm_snippets: int) -> None:
        from logging import getLogger

        logger = getLogger(__name__)
        logger.info(
            "chat.context.loaded",
            extra={"stm_turns": stm_turns, "ltm_snippets": ltm_snippets},
        )

    def _craft_reply(self, user_text: str, lang: str) -> str:
        if lang.lower().startswith("zh"):
            return (
                f"你说「{user_text.strip()}」，这很有意思！我在这儿，随时可以继续聊聊。"
                " 如果你愿意，也可以告诉我你现在在做什么～"
            )
        return (
            f"You said: '{user_text.strip()}'. That sounds interesting! I'm here to chat whenever you like. "
            "Feel free to share what you're up to!"
        )

    def _craft_image_reply(self, prompt_text: str, lang: str) -> str:
        display_prompt = prompt_text.strip() if prompt_text else ""
        if lang.lower().startswith("zh"):
            if display_prompt:
                return (
                    f"这张图片听起来很有意思！虽然我暂时看不到实际画面，"
                    f"但根据你的提示「{display_prompt}」我可以和你一起展开想象。"
                    "要不要再告诉我一些细节？"
                )
            return (
                "这张图片看起来很有意思！虽然我暂时无法直接看到内容，"
                "但如果你描述更多细节，我会和你一起展开想象。"
            )
        if display_prompt:
            return (
                "That picture sounds fascinating! I can't see it directly right now, "
                f"but with your hint \"{display_prompt}\" we can imagine it together. "
                "Feel free to share more details!"
            )
        return (
            "That picture sounds fascinating! I can't view it directly, but if you describe a few more details "
            "we can imagine it together."
        )
