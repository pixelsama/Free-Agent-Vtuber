from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(slots=True)
class AudioPayload:
    """Raw audio payload supplied by clients."""

    data: bytes
    content_type: str
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    duration_seconds: Optional[float] = None
    extra: Mapping[str, str] | None = None


@dataclass(slots=True)
class AudioMetadata:
    """Normalized metadata emitted by preprocessing."""

    sample_rate: int
    channels: int
    duration_seconds: float
    format: str


@dataclass(slots=True)
class AudioBundle:
    """Preprocessed audio ready for ASR consumption."""

    pcm: bytes
    metadata: AudioMetadata
