from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(slots=True)
class AsrOptions:
    lang: Optional[str] = None
    enable_timestamps: bool = False
    sample_rate: Optional[int] = None


@dataclass(slots=True)
class AsrPartial:
    text: str
    confidence: Optional[float] = None
    is_final: bool = False


@dataclass(slots=True)
class AsrResult:
    text: str
    partials: Iterable[AsrPartial] | None = None
    duration_seconds: Optional[float] = None
    provider: Optional[str] = None
