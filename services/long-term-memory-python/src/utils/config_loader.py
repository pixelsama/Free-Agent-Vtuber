"""
配置加载器
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml


logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器，支持从环境变量覆盖"""
    
    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 从环境变量覆盖配置
        self._override_from_env(config)
        return config
    
    def _override_from_env(self, config: Dict[str, Any]) -> None:
        """从环境变量覆盖配置"""
        # Redis配置
        if "redis" in config:
            config["redis"]["host"] = os.getenv("REDIS_HOST", config["redis"]["host"])
            config["redis"]["port"] = int(os.getenv("REDIS_PORT", config["redis"]["port"]))
            config["redis"]["db"] = int(os.getenv("REDIS_DB", config["redis"]["db"]))
        
        # Qdrant配置
        if "qdrant" in config:
            config["qdrant"]["host"] = os.getenv("QDRANT_HOST", config["qdrant"]["host"])
            config["qdrant"]["port"] = int(os.getenv("QDRANT_PORT", config["qdrant"]["port"]))
        
        # Mem0配置
        if "mem0" in config:
            mem0_cfg = config["mem0"]
            mem0_cfg["config_path"] = os.getenv("MEM0_CONFIG_PATH", mem0_cfg.get("config_path"))

            llm_provider = os.getenv("MEM0_LLM_PROVIDER")
            if llm_provider:
                mem0_cfg["llm_provider"] = llm_provider

            embedder_provider = os.getenv("MEM0_EMBEDDER_PROVIDER")
            if embedder_provider:
                mem0_cfg["embedding_provider"] = embedder_provider

            llm_cfg_raw = os.getenv("MEM0_LLM_CONFIG_JSON")
            if llm_cfg_raw:
                try:
                    mem0_cfg["llm_config"] = json.loads(llm_cfg_raw)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in MEM0_LLM_CONFIG_JSON; ignoring override")

            embed_cfg_raw = os.getenv("MEM0_EMBEDDER_CONFIG_JSON")
            if embed_cfg_raw:
                try:
                    mem0_cfg["embedding_config"] = json.loads(embed_cfg_raw)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in MEM0_EMBEDDER_CONFIG_JSON; ignoring override")
        
        # 服务配置
        if "service" in config:
            config["service"]["host"] = os.getenv("SERVICE_HOST", config["service"]["host"])
            config["service"]["port"] = int(os.getenv("SERVICE_PORT", config["service"]["port"]))
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点分隔符"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置"""
        return self.get("redis", {})
    
    def get_qdrant_config(self) -> Dict[str, Any]:
        """获取Qdrant配置"""
        return self.get("qdrant", {})
    
    def get_mem0_config(self) -> Dict[str, Any]:
        """获取Mem0配置"""
        return self.get("mem0", {})
    
    def get_channels_config(self) -> Dict[str, str]:
        """获取频道配置"""
        return self.get("channels", {})
    
    def get_queues_config(self) -> Dict[str, str]:
        """获取队列配置"""
        return self.get("queues", {})
    
    def load_mem0_yaml_config(self) -> Dict[str, Any]:
        """加载Mem0 YAML配置文件"""
        mem0_config_path = self.get("mem0.config_path")
        if not mem0_config_path:
            raise ValueError("Mem0配置路径未设置")
        
        yaml_path = Path(mem0_config_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Mem0配置文件不存在: {yaml_path}")
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)


# 全局配置实例
config_loader = ConfigLoader()
