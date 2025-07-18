from typing import Dict, Type, List
from .tts_provider import TTSProvider

class ProviderFactory:
    """
    A factory for creating TTS provider instances.
    """
    _providers: Dict[str, Type[TTSProvider]] = {}

    @staticmethod
    def register_provider(name: str, provider_class: Type[TTSProvider]) -> None:
        """
        Registers a new TTS provider.

        Args:
            name (str): The name of the provider.
            provider_class (Type[TTSProvider]): The provider class.
        """
        ProviderFactory._providers[name] = provider_class

    @staticmethod
    def create_provider(provider_name: str, config: dict) -> TTSProvider:
        """
        Creates an instance of a registered TTS provider.

        Args:
            provider_name (str): The name of the provider to create.
            config (dict): The configuration for the provider.

        Returns:
            TTSProvider: An instance of the TTS provider.

        Raises:
            ValueError: If the provider is not registered.
        """
        provider_class = ProviderFactory._providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"Provider '{provider_name}' is not registered.")
        
        provider_instance = provider_class(config)
        return provider_instance

    @staticmethod
    def get_available_providers() -> List[str]:
        """
        Gets a list of available (registered) providers.

        Returns:
            List[str]: A list of provider names.
        """
        return list(ProviderFactory._providers.keys())
