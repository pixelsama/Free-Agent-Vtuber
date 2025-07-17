import json
import os
from typing import Dict, Any

class ConfigManager:
    """
    Manages loading, validation, and access to the configuration.
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self.load_config(config_path)

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Loads the configuration file and replaces environment variables.

        Args:
            config_path (str): The path to the configuration file.

        Returns:
            Dict[str, Any]: The loaded configuration.
        """
        with open(config_path, 'r') as f:
            config_str = f.read()

        # Replace environment variables
        config_str = os.path.expandvars(config_str)

        config = json.loads(config_str)
        self.validate_config(config)
        return config

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validates the structure of the configuration.

        Args:
            config (Dict[str, Any]): The configuration to validate.

        Returns:
            bool: True if the configuration is valid.

        Raises:
            ValueError: If the configuration is invalid.
        """
        required_keys = ["redis", "tts", "providers", "logging"]
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration section: {key}")
        
        # Add more specific validation as needed
        if "default_provider" not in config["tts"]:
            raise ValueError("Missing 'default_provider' in 'tts' config section.")

        return True

    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """
        Gets the configuration for a specific TTS provider.

        Args:
            provider_name (str): The name of the provider.

        Returns:
            Dict[str, Any]: The provider's configuration.
        """
        return self.config.get("providers", {}).get(provider_name, {})

    def reload_config(self) -> None:
        """
        Reloads the configuration from the file.
        """
        self.config = self.load_config(self.config_path)

    def get_config(self) -> Dict[str, Any]:
        """
        Returns the entire configuration dictionary.

        Returns:
            Dict[str, Any]: The configuration.
        """
        return self.config
