#!/usr/bin/env python3

import sys
import os
from pathlib import Path

# 添加共享工具路径
current_dir = Path(__file__).parent
shared_utils_path = current_dir / "shared_utils"
if shared_utils_path.exists():
    sys.path.insert(0, str(shared_utils_path))

# 添加项目根目录的utils路径
utils_path = current_dir / "utils"
if not utils_path.exists():
    utils_path = current_dir.parent.parent / "utils"

if utils_path.exists():
    sys.path.insert(0, str(utils_path))

try:
    from hot_reload import create_dev_runner
    
    if __name__ == "__main__":
        print("启动 Letta Bridge 服务开发模式...")
        manager = create_dev_runner(
            main_module="main",
            watch_patterns=['.py', '.json'],
            ignore_patterns=['__pycache__', '.pyc', '.git', 'venv/', 'tests/', '.log'],
            debounce_seconds=1.0
        )
        manager.run()
        
except ImportError as e:
    print(f"热重载模块导入失败: {e}")
    print("回退到直接运行模式...")
    
    # 回退方案：直接运行main.py
    import subprocess
    subprocess.run([sys.executable, "main.py"])