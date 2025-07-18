import edge_tts
from typing import Dict, Any, List
from .tts_provider import TTSProvider
from .factory import ProviderFactory

class EdgeTTS(TTSProvider):
    """
    TTS provider for Microsoft Edge's Text-to-Speech service.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validate_config(config)
        self.voice = config.get("voice", "zh-CN-XiaoxiaoNeural")
        self.rate = config.get("rate", "+0%")
        self.pitch = config.get("pitch", "+0Hz")

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validates the Edge TTS provider configuration.
        """
        # Edge TTS has fewer mandatory configs, so we just ensure keys exist
        if "voice" not in config:
            print("Warning: 'voice' not set for Edge TTS, using default.")
        return True

    async def synthesize(self, text: str, **kwargs) -> bytes:
        """
        Synthesizes text to speech using the edge-tts library.
        """
        voice = kwargs.get("voice", self.voice)
        rate = kwargs.get("rate", self.rate)
        pitch = kwargs.get("pitch", self.pitch)

        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        
        audio_bytes = b""
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
        except Exception as e:
            print(f"Error synthesizing audio with Edge TTS: {e}")
            raise
            
        return audio_bytes

    async def get_supported_voices(self) -> List[str]:
        """
        Gets a list of supported voices from the edge-tts library.
        """
        voices = await edge_tts.list_voices()
        return [voice["ShortName"] for voice in voices]

# Register the provider
ProviderFactory.register_provider("edge", EdgeTTS)
