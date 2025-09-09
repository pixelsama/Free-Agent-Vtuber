#!/usr/bin/env python3
"""
长期记忆服务开发环境热更新运行器

使用watchdog监控文件变化，自动重启服务
"""
import sys
import os
import signal
import subprocess
import time
from pathlib import Path

# 添加共享工具路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'shared_utils'))

try:
    from utils.hot_reload import HotReloadManager
except ImportError:
    print("警告: 未找到热更新工具，使用基础重启功能")
    HotReloadManager = None

class LTMDevRunner:
    """长期记忆服务开发运行器"""
    
    def __init__(self):
        self.process = None
        self.service_path = Path(__file__).parent
        
    def start_service(self):
        """启动长期记忆服务"""
        try:
            if self.process:
                self.stop_service()
            
            print(f"🚀 启动长期记忆服务... (PID: {os.getpid()})")
            self.process = subprocess.Popen([
                sys.executable, "main.py"
            ], cwd=self.service_path)
            
            return self.process
            
        except Exception as e:
            print(f"❌ 服务启动失败: {e}")
            return None
    
    def stop_service(self):
        """停止长期记忆服务"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                print("🛑 长期记忆服务已停止")
            except subprocess.TimeoutExpired:
                self.process.kill()
                print("💀 强制停止长期记忆服务")
            except Exception as e:
                print(f"⚠️ 停止服务时出错: {e}")
            finally:
                self.process = None
    
    def restart_service(self):
        """重启服务"""
        print("🔄 重启长期记忆服务...")
        self.stop_service()
        time.sleep(1)  # 等待端口释放
        return self.start_service()
    
    def run_with_hot_reload(self):
        """运行服务并启用热更新"""
        if not HotReloadManager:
            return self.run_basic()
        
        def on_file_changed(file_path):
            print(f"📝 检测到文件变更: {file_path}")
            self.restart_service()
        
        # 启动服务
        self.start_service()
        
        # 启动热更新监控
        hot_reload = HotReloadManager(
            watch_directory=str(self.service_path),
            callback=on_file_changed,
            patterns=["*.py", "*.json", "*.yaml", "*.yml"],
            ignore_patterns=["*__pycache__*", "*.pyc", "*/.git/*", "*/logs/*"]
        )
        
        try:
            print("🔥 热更新已启用，监控文件变化中...")
            hot_reload.start()
            
            # 主循环
            while True:
                if self.process and self.process.poll() is not None:
                    print("⚠️ 服务进程意外退出，正在重启...")
                    self.restart_service()
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🔚 收到中断信号，正在关闭...")
        finally:
            hot_reload.stop()
            self.stop_service()
    
    def run_basic(self):
        """基础运行模式（无热更新）"""
        print("⚠️ 基础模式运行（无热更新功能）")
        
        def signal_handler(signum, frame):
            print(f"\n收到信号 {signum}，正在关闭服务...")
            self.stop_service()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动服务
        process = self.start_service()
        if not process:
            sys.exit(1)
        
        try:
            # 等待服务进程结束
            process.wait()
        except KeyboardInterrupt:
            print("\n正在关闭服务...")
        finally:
            self.stop_service()

def main():
    """主入口函数"""
    print("🧠 长期记忆服务开发环境启动器")
    print("=" * 50)
    
    runner = LTMDevRunner()
    
    # 检查是否有热更新支持
    if HotReloadManager:
        runner.run_with_hot_reload()
    else:
        runner.run_basic()

if __name__ == "__main__":
    main()