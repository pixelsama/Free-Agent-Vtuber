import logging
from typing import Dict, Any

def setup_logger(config: Dict[str, Any]):
    """
    Sets up the logger based on the provided configuration.
    """
    log_config = config.get("logging", {})
    level = log_config.get("level", "INFO").upper()
    log_format = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_file = log_config.get("file")

    logging.basicConfig(level=level, format=log_format)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)

    return logging.getLogger("TTSService")
