from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from .types import AudioPayload


@dataclass(slots=True)
class IngestLimits:
    max_bytes: int
    max_duration_seconds: float


class AudioIngestor:
    """Parses inbound requests into AudioPayload objects."""

    def __init__(self, *, limits: IngestLimits) -> None:
        self._limits = limits

    async def from_bytes(self, *, data: bytes, content_type: str, meta: Optional[dict[str, Any]] = None) -> AudioPayload:
        self._enforce_size(len(data))
        return AudioPayload(data=data, content_type=content_type, extra=meta or {})

    async def from_upload(self, *, file_reader: Callable[[], Awaitable[bytes]], content_type: str, meta: Optional[dict[str, Any]] = None) -> AudioPayload:
        data = await file_reader()
        return await self.from_bytes(data=data, content_type=content_type, meta=meta)

    def _enforce_size(self, size: int) -> None:
        if size > self._limits.max_bytes:
            raise ValueError("audio payload exceeds configured size limit")
