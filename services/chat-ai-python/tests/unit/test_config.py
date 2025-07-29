import pytest
import json
import os
from unittest.mock import mock_open, patch
from pathlib import Path

from main import load_config


class TestConfig:
    """配置加载测试"""
    
    def test_load_config_success(self):
        """测试成功加载配置"""
        # 创建模拟的配置数据
        mock_config = {
            "ai": {
                "provider": "openai_compatible",
                "api_base": "https://test-api.example.com/v1",
                "api_key": "test-key"
            },
            "redis": {
                "host": "localhost",
                "port": 6379
            }
        }
        
        # 使用patch模拟文件读取
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            with patch("pathlib.Path.exists", return_value=True):
                result = load_config()
                assert result is True
    
    def test_load_config_file_not_found(self):
        """测试配置文件不存在"""
        # 使用patch模拟文件不存在
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            result = load_config()
            assert result is False
    
    def test_load_config_invalid_json(self):
        """测试无效的JSON配置"""
        # 使用patch模拟无效的JSON
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch("pathlib.Path.exists", return_value=True):
                result = load_config()
                assert result is False
    
    def test_load_config_empty_file(self):
        """测试空配置文件"""
        # 使用patch模拟空文件
        with patch("builtins.open", mock_open(read_data="")):
            with patch("pathlib.Path.exists", return_value=True):
                result = load_config()
                assert result is False
