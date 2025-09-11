from pathlib import Path

from src.services.tts_service import TTSService


def test_tts_service_loads_config():
    config_path = Path(__file__).resolve().parents[2] / "config" / "config.json"
    service = TTSService(str(config_path))
    assert service.default_provider_name == service.config["tts"]["default_provider"]
