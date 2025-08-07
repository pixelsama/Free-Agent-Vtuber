import os
import types
import pytest

from providers.factory import build_provider
from providers.funasr_local import FunASRLocalProvider


@pytest.mark.asyncio
async def test_build_provider_funasr_local(monkeypatch):
    # monkeypatch AutoModel 以避免真实依赖与下载
    class DummyAutoModel:
        def __init__(self, model: str, **kwargs):
            self.model = model
            self.kwargs = kwargs

        def generate(self, input: str, device: str = "cpu"):
            # 返回与 FunASR 常见结构相似的结果
            return {"text": "你好，世界"}

    # 构造一个假的 funasr 模块并注入到 sys.modules
    dummy_funasr = types.SimpleNamespace(AutoModel=DummyAutoModel)
    monkeypatch.setitem(__import__("sys").modules, "funasr", dummy_funasr)

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
async def test_funasr_transcribe_file_success(monkeypatch, tmp_path):
    # 伪造音频文件
    wav_path = tmp_path / "demo.wav"
    wav_path.write_bytes(b"RIFFxxxxWAVEfmt ")  # 仅占位，Provider 只检查文件存在

    class DummyAutoModel:
        def __init__(self, model: str, **kwargs):
            self.model = model
            self.kwargs = kwargs

        def generate(self, input: str, device: str = "cpu"):
            assert os.path.isfile(input)
            return {"text": "单元测试文本"}

    dummy_funasr = types.SimpleNamespace(AutoModel=DummyAutoModel)
    monkeypatch.setitem(__import__("sys").modules, "funasr", dummy_funasr)

    provider = FunASRLocalProvider(
        model_id="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        device="cpu",
        cache_dir=None,
    )

    result = await provider.transcribe_file(str(wav_path), lang="zh", timestamps=False, diarization=False)
    assert result.text == "单元测试文本"
    assert result.words == []
    assert result.lang == "zh"
    assert result.provider_meta.get("provider") == "funasr_local"
    assert "model" in result.provider_meta


@pytest.mark.asyncio
async def test_funasr_transcribe_file_missing(monkeypatch):
    class DummyAutoModel:
        def __init__(self, model: str, **kwargs):
            pass

        def generate(self, input: str, device: str = "cpu"):
            return {"text": "should not be called"}

    dummy_funasr = types.SimpleNamespace(AutoModel=DummyAutoModel)
    monkeypatch.setitem(__import__("sys").modules, "funasr", dummy_funasr)

    provider = FunASRLocalProvider(
        model_id="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        device="cpu",
        cache_dir=None,
    )

    with pytest.raises(FileNotFoundError):
        await provider.transcribe_file("/no/such/file.wav", lang="zh", timestamps=False, diarization=False)


@pytest.mark.asyncio
async def test_funasr_model_load_failure(monkeypatch):
    # 让 AutoModel 构造抛错，验证错误映射
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
