from __future__ import annotations

from typing import Any, Dict

from .asr_provider import BaseASRProvider
from .asr_provider import ASRResult, ASRWord  # re-export if needed


class FakeProvider(BaseASRProvider):
    async def transcribe_file(self, path: str, lang: str | None, timestamps: bool, diarization: bool) -> ASRResult:
        # 返回固定文本，便于联调与测试
        return ASRResult(
            text="测试文本",
            words=[],
            lang=lang or "zh",
            provider_meta={"provider": "fake"},
        )


def build_provider(name: str, provider_cfg: Dict[str, Any]) -> BaseASRProvider:
    lname = (name or "").lower()
    if lname in ("fake", "stub"):
        return FakeProvider()
    if lname in ("openai_whisper", "whisper", "openai"):
        # 延迟导入以避免无依赖环境下报错
        try:
            from .openai_whisper import OpenAIWhisperProvider
        except Exception as e:
            raise RuntimeError(f"OpenAI Whisper provider not available: {e}")
        creds = provider_cfg.get("credentials", {}) if isinstance(provider_cfg, dict) else {}
        api_key_env = creds.get("api_key_env", "OPENAI_API_KEY")
        base_url = creds.get("base_url", "https://api.openai.com/v1")
        return OpenAIWhisperProvider(api_key_env=api_key_env, base_url=base_url)
    if lname in ("funasr_local", "funasr"):
        # FunASR 本地推理 Provider（需要 funasr/modelscope 依赖）
        try:
            from .funasr_local import FunASRLocalProvider
        except Exception as e:
            raise RuntimeError(f"FunASR provider not available: {e}")
        options = provider_cfg.get("options", {}) if isinstance(provider_cfg, dict) else {}
        model_id = options.get(
            "model_id",
            "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        )
        device = options.get("device", "cpu")
        cache_dir = options.get("cache_dir")
        return FunASRLocalProvider(model_id=model_id, device=device, cache_dir=cache_dir)
    raise ValueError(f"Unsupported ASR provider: {name}")
