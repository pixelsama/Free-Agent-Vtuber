import httpx
from typing import Dict, Any, List
from .tts_provider import TTSProvider
from .factory import ProviderFactory

class OpenAITTS(TTSProvider):
    """
    TTS provider for OpenAI's Text-to-Speech API.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validate_config(config)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "tts-1")
        self.voice = config.get("voice", "alloy")
        self.speed = config.get("speed", 1.0)
        self.response_format = config.get("response_format", "mp3")
        self.base_url = "https://api.openai.com/v1/audio/speech"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validates the OpenAI provider configuration.
        """
        if not config.get("api_key"):
            raise ValueError("OpenAI TTS provider requires 'api_key' in config.")
        return True

    async def synthesize(self, text: str, **kwargs) -> bytes:
        """
        Synthesizes text to speech using OpenAI's API.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": kwargs.get("model", self.model),
            "input": text,
            "voice": kwargs.get("voice", self.voice),
            "speed": kwargs.get("speed", self.speed),
            "response_format": self.response_format,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, headers=headers, json=data, timeout=30.0)
                response.raise_for_status()
                return response.content
            except httpx.HTTPStatusError as e:
                # Log the error details
                print(f"Error synthesizing audio with OpenAI: {e.response.text}")
                raise
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                raise

    def get_supported_voices(self) -> List[str]:
        return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def get_supported_models(self) -> List[str]:
        return ["tts-1", "tts-1-hd"]

# Register the provider
ProviderFactory.register_provider("openai", OpenAITTS)
