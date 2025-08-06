from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, RootModel, field_validator, model_validator


# -----------------------------
# 配置模型
# -----------------------------
class ServiceConfig(BaseModel):
    name: str = Field(default="asr-python")
    concurrency: int = Field(default=2, ge=1, le=64)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0)
    tasks_queue: str = "asr_tasks"
    results_channel: str = "asr_results"


class ProviderCredentials(BaseModel):
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None


class ProviderOptions(BaseModel):
    lang: str | Literal["auto"] = "auto"
    timestamps: bool = True
    diarization: bool = False


class ProviderConfig(BaseModel):
    name: str = "fake"
    timeout_sec: int = Field(default=60, ge=1, le=600)
    max_retries: int = Field(default=1, ge=0, le=10)
    options: ProviderOptions = Field(default_factory=ProviderOptions)
    credentials: ProviderCredentials = Field(default_factory=ProviderCredentials)


class AudioConfig(BaseModel):
    target_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    max_duration_sec: int = Field(default=300, ge=1, le=3600)


class AppConfig(BaseModel):
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)


# -----------------------------
# 消息模型
# -----------------------------
class AudioMessage(BaseModel):
    type: Literal["file"] = "file"
    path: str
    format: Literal["wav", "pcm_s16le", "mp3"] = "wav"
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)

    @field_validator("path")
    @classmethod
    def must_be_abs_path(cls, v: str) -> str:
        # 仅校验非空；是否绝对路径交由网关控制（容器间路径可能不同）
        if not v or not isinstance(v, str):
            raise ValueError("audio.path is required")
        return v


class TaskOptions(BaseModel):
    lang: Optional[str] = None
    timestamps: bool = True
    diarization: bool = False


class TaskMeta(BaseModel):
    source: Optional[str] = None
    trace_id: Optional[str] = None


class TaskMessage(BaseModel):
    task_id: str
    audio: AudioMessage
    options: TaskOptions = Field(default_factory=TaskOptions)
    meta: TaskMeta = Field(default_factory=TaskMeta)


class WordInfo(BaseModel):
    start: Optional[float] = None
    end: Optional[float] = None
    word: Optional[str] = None
    conf: Optional[float] = None


class ResultStatus(RootModel[Literal["finished", "failed", "partial"]]):
    pass


class ResultMessage(BaseModel):
    task_id: str
    status: Literal["finished", "failed", "partial"]
    text: Optional[str] = None
    words: List[WordInfo] = Field(default_factory=list)
    provider: Optional[str] = None
    lang: Optional[str] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> "ResultMessage":
        if self.status == "finished":
            if not self.text:
                raise ValueError("finished result must contain text")
        if self.status == "failed":
            if not self.error:
                raise ValueError("failed result must contain error")
        return self
