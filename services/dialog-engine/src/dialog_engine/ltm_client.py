from __future__ import annotations

"""Inline LTM retrieval client for dialog-engine."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LTMInlineClient:
    def __init__(
        self,
        *,
        base_url: Optional[str],
        retrieve_path: str,
        timeout: float,
        max_snippets: int,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._path = retrieve_path or "/v1/memory/retrieve"
        self._timeout = timeout
        self._max_snippets = max_snippets

    def is_configured(self) -> bool:
        return bool(self._base_url)

    async def retrieve(
        self,
        *,
        session_id: str,
        user_text: str,
        meta: Dict[str, Any],
        limit: Optional[int] = None,
    ) -> List[str]:
        if not self.is_configured():
            return []

        max_items = limit or self._max_snippets
        if max_items <= 0:
            return []

        payload = {
            "sessionId": session_id,
            "query": user_text,
            "meta": meta,
            "limit": max_items,
        }

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                response = await client.post(self._path, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.warning("ltm.retrieve.error", extra={"error": repr(exc)})
            return []

        items = data.get("results") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []

        snippets: List[str] = []
        for item in items[:max_items]:
            if isinstance(item, dict):
                content = item.get("content") or item.get("memory") or item.get("text")
            else:
                content = str(item)
            if content:
                snippets.append(str(content).strip())
        return snippets


__all__ = ["LTMInlineClient"]
