import os
import types

import pytest

from src.services.providers.factory import build_provider
from src.services.providers.funasr_local import FunASRLocalProvider


@pytest.mark.asyncio
async def test_build_provider_funasr_local(dummy_funasr):
    provider = build_provider(
        "funasr_local",
        {
            "options": {
                "model_id": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                "device": "cpu",
                "cache_dir": None,
            }
        },
    )
    assert isinstance(provider, FunASRLocalProvider)


@pytest.mark.asyncio
async def test_funasr_transcribe_file_success(dummy_funasr, tmp_path):
    wav_path = tmp_path / "demo.wav"
    wav_path.write_bytes(b"RIFFxxxxWAVEfmt ")

    provider = FunASRLocalProvider(
        model_id="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        device="cpu",
        cache_dir=None,
    )

    result = await provider.transcribe_file(
        str(wav_path), lang="zh", timestamps=False, diarization=False
    )
    assert result.text == "你好，世界"
    assert result.words == []
    assert result.lang == "zh"
    assert result.provider_meta.get("provider") == "funasr_local"
    assert "model" in result.provider_meta


@pytest.mark.asyncio
async def test_funasr_transcribe_file_missing(dummy_funasr):
    provider = FunASRLocalProvider(
        model_id="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        device="cpu",
        cache_dir=None,
    )

    with pytest.raises(FileNotFoundError):
        await provider.transcribe_file(
            "/no/such/file.wav", lang="zh", timestamps=False, diarization=False
        )


@pytest.mark.asyncio
async def test_funasr_model_load_failure(monkeypatch):
    class BrokenAutoModel:
        def __init__(self, model: str, **kwargs):
            raise RuntimeError("mock load error")

    dummy_funasr = types.SimpleNamespace(AutoModel=BrokenAutoModel)
    monkeypatch.setitem(__import__("sys").modules, "funasr", dummy_funasr)

    with pytest.raises(RuntimeError) as ei:
        FunASRLocalProvider(
            model_id="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            device="cpu",
            cache_dir=None,
        )
    assert "Failed to load FunASR model" in str(ei.value)
