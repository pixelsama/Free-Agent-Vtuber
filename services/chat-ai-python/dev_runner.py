#!/usr/bin/env python3
"""
Chat AI 服务开发环境热重载启动器
"""
import sys
import os
from pathlib import Path

# 添加共享 utils 目录到 Python 路径
shared_utils_path = Path(__file__).parent / "shared_utils"
sys.path.insert(0, str(shared_utils_path))

from hot_reload import create_dev_runner

def main():
    """启动 Chat AI 服务的热重载开发环境"""
    
    # 配置热重载参数
    manager = create_dev_runner(
        main_module="main",
        watch_patterns=['.py', '.json'],  # 监控 Python 和配置文件
        ignore_patterns=[
            '__pycache__', '.pyc', '.pyo', '.git', '.venv', 'venv',
            '.pytest_cache', '.coverage', '.log', 'tests'
        ],
        debounce_seconds=1.0  # 1秒防抖
    )
    
    # 设置工作目录为服务目录
    os.chdir(Path(__file__).parent)
    
    # 启动热重载管理器
    manager.run()

if __name__ == "__main__":
    main()