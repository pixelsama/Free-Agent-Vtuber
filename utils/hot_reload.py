"""
热重载模块 - 用于纯 Python 微服务的开发环境自动重启
支持基于 watchdog 的文件监控和进程重启
"""
import os
import sys
import time
import signal
import subprocess
import threading
import logging
from pathlib import Path
from typing import List, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HotReloadHandler(FileSystemEventHandler):
    """文件系统事件处理器"""
    
    def __init__(self, restart_callback: Callable[[], None], 
                 watch_patterns: List[str] = None,
                 ignore_patterns: List[str] = None,
                 debounce_seconds: float = 1.0):
        """
        初始化热重载处理器
        
        Args:
            restart_callback: 重启回调函数
            watch_patterns: 监控的文件模式列表 (如 ['.py', '.json'])
            ignore_patterns: 忽略的文件模式列表 (如 ['__pycache__', '.pyc'])
            debounce_seconds: 防抖延迟时间（秒）
        """
        self.restart_callback = restart_callback
        self.watch_patterns = watch_patterns or ['.py', '.json']
        self.ignore_patterns = ignore_patterns or [
            '__pycache__', '.pyc', '.pyo', '.git', '.venv', 'venv',
            '.pytest_cache', '.coverage', '.log'
        ]
        self.debounce_seconds = debounce_seconds
        self.last_restart_time = 0
        self._restart_timer: Optional[threading.Timer] = None
        
    def should_restart_for_path(self, file_path: str) -> bool:
        """检查文件路径是否应该触发重启"""
        path = Path(file_path)
        
        # 检查是否匹配忽略模式
        for ignore in self.ignore_patterns:
            if ignore in str(path):
                return False
        
        # 检查是否匹配监控模式
        for pattern in self.watch_patterns:
            if str(path).endswith(pattern):
                return True
                
        return False
    
    def _debounced_restart(self):
        """防抖重启函数"""
        current_time = time.time()
        if current_time - self.last_restart_time >= self.debounce_seconds:
            self.last_restart_time = current_time
            logger.info("文件变更检测到，正在重启服务...")
            self.restart_callback()
    
    def on_modified(self, event: FileSystemEvent):
        """文件修改事件"""
        if not event.is_directory and self.should_restart_for_path(event.src_path):
            logger.debug(f"文件修改: {event.src_path}")
            self._schedule_restart()
    
    def on_created(self, event: FileSystemEvent):
        """文件创建事件"""
        if not event.is_directory and self.should_restart_for_path(event.src_path):
            logger.debug(f"文件创建: {event.src_path}")
            self._schedule_restart()
    
    def on_moved(self, event: FileSystemEvent):
        """文件移动事件"""
        if hasattr(event, 'dest_path'):
            if not event.is_directory and self.should_restart_for_path(event.dest_path):
                logger.debug(f"文件移动: {event.src_path} -> {event.dest_path}")
                self._schedule_restart()
    
    def _schedule_restart(self):
        """调度重启（带防抖）"""
        if self._restart_timer:
            self._restart_timer.cancel()
        
        self._restart_timer = threading.Timer(self.debounce_seconds, self._debounced_restart)
        self._restart_timer.start()

class HotReloadManager:
    """热重载管理器 - 负责启动、监控和重启进程"""
    
    def __init__(self, main_module: str, 
                 watch_directory: str = None,
                 watch_patterns: List[str] = None,
                 ignore_patterns: List[str] = None,
                 debounce_seconds: float = 1.0):
        """
        初始化热重载管理器
        
        Args:
            main_module: 主模块名称 (如 'main')
            watch_directory: 监控目录路径 (默认为当前目录)
            watch_patterns: 监控的文件模式列表
            ignore_patterns: 忽略的文件模式列表
            debounce_seconds: 防抖延迟时间
        """
        self.main_module = main_module
        self.watch_directory = Path(watch_directory or os.getcwd())
        self.watch_patterns = watch_patterns
        self.ignore_patterns = ignore_patterns
        self.debounce_seconds = debounce_seconds
        
        self.process: Optional[subprocess.Popen] = None
        self.observer: Optional[Observer] = None
        self.handler: Optional[HotReloadHandler] = None
        self._shutdown_event = threading.Event()
        
    def start_process(self) -> subprocess.Popen:
        """启动主进程"""
        try:
            cmd = [sys.executable, f"{self.main_module}.py"]
            logger.info(f"启动进程: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                cwd=self.watch_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1  # 行缓冲
            )
            
            # 启动输出监控线程
            threading.Thread(
                target=self._monitor_process_output, 
                args=(process,), 
                daemon=True
            ).start()
            
            return process
            
        except Exception as e:
            logger.error(f"启动进程失败: {e}")
            raise
    
    def _monitor_process_output(self, process: subprocess.Popen):
        """监控进程输出"""
        try:
            for line in iter(process.stdout.readline, ''):
                if line.strip():
                    print(f"[{self.main_module}] {line.strip()}")
                if self._shutdown_event.is_set():
                    break
        except Exception as e:
            if not self._shutdown_event.is_set():
                logger.error(f"监控进程输出时出错: {e}")
    
    def stop_process(self):
        """停止当前进程"""
        if self.process and self.process.poll() is None:
            try:
                logger.info("正在停止进程...")
                
                # 发送 SIGTERM 信号
                self.process.terminate()
                
                # 等待进程结束，超时后强制杀死
                try:
                    self.process.wait(timeout=5)
                    logger.info("进程已正常结束")
                except subprocess.TimeoutExpired:
                    logger.warning("进程未在超时时间内结束，强制杀死")
                    self.process.kill()
                    self.process.wait()
                    
            except Exception as e:
                logger.error(f"停止进程时出错: {e}")
            finally:
                self.process = None
    
    def restart_process(self):
        """重启进程"""
        logger.info("正在重启服务...")
        self.stop_process()
        time.sleep(0.5)  # 短暂等待确保进程完全结束
        
        try:
            self.process = self.start_process()
            logger.info(f"服务已重启，PID: {self.process.pid}")
        except Exception as e:
            logger.error(f"重启服务失败: {e}")
    
    def start_watching(self):
        """开始文件监控"""
        try:
            self.handler = HotReloadHandler(
                restart_callback=self.restart_process,
                watch_patterns=self.watch_patterns,
                ignore_patterns=self.ignore_patterns,
                debounce_seconds=self.debounce_seconds
            )
            
            self.observer = Observer()
            self.observer.schedule(
                self.handler, 
                str(self.watch_directory), 
                recursive=True
            )
            self.observer.start()
            
            logger.info(f"开始监控目录: {self.watch_directory}")
            logger.info(f"监控文件类型: {self.handler.watch_patterns}")
            
        except Exception as e:
            logger.error(f"启动文件监控失败: {e}")
            raise
    
    def stop_watching(self):
        """停止文件监控"""
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2)
                logger.info("文件监控已停止")
            except Exception as e:
                logger.error(f"停止文件监控时出错: {e}")
            finally:
                self.observer = None
                self.handler = None
    
    def run(self):
        """运行热重载管理器"""
        logger.info(f"启动热重载管理器: {self.main_module}")
        logger.info(f"Python 版本: {sys.version}")
        logger.info(f"工作目录: {self.watch_directory}")
        
        # 设置信号处理
        def signal_handler(signum, frame):
            logger.info(f"接收到信号 {signum}，正在关闭...")
            self.shutdown()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # 启动进程
            self.process = self.start_process()
            
            # 启动文件监控
            self.start_watching()
            
            # 主循环 - 保持运行直到收到停止信号
            while not self._shutdown_event.is_set():
                time.sleep(1)
                
                # 检查进程是否意外退出
                if self.process and self.process.poll() is not None:
                    return_code = self.process.returncode
                    if return_code != 0:
                        logger.error(f"进程异常退出，返回码: {return_code}")
                        # 等待一段时间后重启
                        time.sleep(2)
                        self.restart_process()
                    else:
                        logger.info("进程正常退出")
                        break
                        
        except KeyboardInterrupt:
            logger.info("接收到键盘中断")
        except Exception as e:
            logger.error(f"运行时出错: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """关闭热重载管理器"""
        logger.info("正在关闭热重载管理器...")
        self._shutdown_event.set()
        
        # 停止文件监控
        self.stop_watching()
        
        # 停止进程
        self.stop_process()
        
        logger.info("热重载管理器已关闭")

def create_dev_runner(main_module: str, 
                     watch_patterns: List[str] = None,
                     ignore_patterns: List[str] = None,
                     debounce_seconds: float = 1.0) -> HotReloadManager:
    """
    创建开发运行器的便捷函数
    
    Args:
        main_module: 主模块名称
        watch_patterns: 监控的文件模式列表
        ignore_patterns: 忽略的文件模式列表
        debounce_seconds: 防抖延迟时间
        
    Returns:
        HotReloadManager 实例
    """
    return HotReloadManager(
        main_module=main_module,
        watch_patterns=watch_patterns,
        ignore_patterns=ignore_patterns,
        debounce_seconds=debounce_seconds
    )