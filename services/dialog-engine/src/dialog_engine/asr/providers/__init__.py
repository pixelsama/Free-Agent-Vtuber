"""ASR provider implementations."""

from .base import AsrProvider
from .mock import MockAsrProvider

try:
    from .whisper import WhisperAsrProvider
except RuntimeError:  # pragma: no cover - optional dependency missing
    WhisperAsrProvider = None  # type: ignore[assignment]
except Exception:  # pragma: no cover - defensive guard
    WhisperAsrProvider = None  # type: ignore[assignment]

__all__ = [
    "AsrProvider",
    "MockAsrProvider",
    "WhisperAsrProvider",
]
