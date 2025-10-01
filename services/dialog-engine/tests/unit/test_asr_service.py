import dataclasses

import pytest

from dialog_engine.asr.providers.mock import MockAsrProvider
from dialog_engine.asr.service import AsrService
from dialog_engine.settings import AsrSettings


def _default_asr_settings() -> AsrSettings:
    return AsrSettings(
        enabled=True,
        provider="mock",
        max_bytes=1024 * 1024,
        max_duration_seconds=300.0,
        target_sample_rate=16000,
        target_channels=1,
        default_lang="zh",
        whisper_model="base",
        whisper_device="auto",
        whisper_compute_type="int8",
        whisper_beam_size=1,
        whisper_cache_dir=None,
    )


def test_asr_service_from_settings_mock():
    service = AsrService.from_settings(_default_asr_settings())

    assert isinstance(service.provider, MockAsrProvider)


def test_asr_service_from_settings_unknown_provider():
    cfg = dataclasses.replace(_default_asr_settings(), provider="unknown")

    with pytest.raises(RuntimeError):
        AsrService.from_settings(cfg)
