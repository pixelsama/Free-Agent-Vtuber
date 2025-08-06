from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# 结果数据模型（与 schemas.ResultMessage 的字段对齐，但供 Provider 内部使用）
class ASRWord(BaseModel):
    start: Optional[float] = None
    end: Optional[float] = None
    word: Optional[str] = None
    conf: Optional[float] = None


class ASRResult(BaseModel):
    text: str = ""
    words: List[ASRWord] = Field(default_factory=list)
    lang: Optional[str] = None
    provider_meta: Dict[str, Any] = Field(default_factory=dict)


class BaseASRProvider:
    async def transcribe_file(
        self,
        path: str,
        lang: Optional[str],
        timestamps: bool,
        diarization: bool,
    ) -> ASRResult:
        raise NotImplementedError("Provider must implement transcribe_file")
