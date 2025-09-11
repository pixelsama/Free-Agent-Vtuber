from abc import ABC, abstractmethod
from typing import List

class TTSProvider(ABC):
    """
    Abstract base class for TTS providers.
    """

    @abstractmethod
    async def synthesize(self, text: str, **kwargs) -> bytes:
        """
        Synthesizes text to speech.

        Args:
            text (str): The text to synthesize.
            **kwargs: Provider-specific parameters.

        Returns:
            bytes: The audio data in bytes.
        """
        pass

    @abstractmethod
    def validate_config(self, config: dict) -> bool:
        """
        Validates the provider-specific configuration.

        Args:
            config (dict): The configuration dictionary for the provider.

        Returns:
            bool: True if the configuration is valid, False otherwise.
        """
        pass

    def get_supported_voices(self) -> List[str]:
        """
        Gets a list of supported voices for the provider.

        Returns:
            List[str]: A list of voice names.
        """
        return []

    def get_supported_models(self) -> List[str]:
        """
        Gets a list of supported models for the provider.

        Returns:
            List[str]: A list of model names.
        """
        return []
