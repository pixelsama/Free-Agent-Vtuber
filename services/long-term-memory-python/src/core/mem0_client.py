"""
Mem0框架客户端 - TDD循环2重构优化版本

重构改进（内部优化，API不变）：
1. 懒加载客户端初始化，避免构造函数阻塞
2. 专用线程池优化异步性能
3. 增强错误处理和输入验证
4. 改进日志记录和监控
5. 自动资源管理，用户无需关心生命周期
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from mem0 import Memory
from src.models.memory import UserMemory, MemoryMetadata, MemoryCategory


class Mem0OperationError(Exception):
    """Mem0操作错误"""
    pass


class Mem0Service:
    """Mem0长期记忆服务客户端
    
    重构改进（内部优化，API不变）：
    - 懒加载：首次使用时自动初始化，避免构造函数阻塞
    - 线程池：专用线程池优化异步操作性能
    - 错误处理：增强的错误类型和输入验证
    - 资源管理：自动清理，用户无需关心生命周期
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._client: Optional[Memory] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._init_lock = asyncio.Lock()
        
        # 懒加载：不在构造函数中初始化，避免阻塞
        
    async def _ensure_client(self) -> None:
        """懒加载客户端初始化（线程安全）"""
        if self._client is not None:
            return
            
        # 使用锁避免并发初始化
        async with self._init_lock:
            if self._client is not None:  # 双重检查
                return
                
            try:
                # 创建专用线程池
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(
                        max_workers=4, 
                        thread_name_prefix="mem0-"
                    )
                
                # 在线程池中初始化客户端
                config_path = self.config.get("config_path", "config/mem0_config.yaml")
                
                if not Path(config_path).exists():
                    self.logger.warning(f"Mem0配置文件不存在: {config_path}，使用默认配置")
                    mem0_config = self._get_default_config()
                    self._client = await asyncio.get_event_loop().run_in_executor(
                        self._executor,
                        Memory.from_config,
                        mem0_config
                    )
                else:
                    self._client = await asyncio.get_event_loop().run_in_executor(
                        self._executor,
                        Memory.from_config,
                        config_path
                    )
                
                self.logger.info("Mem0客户端初始化成功")
                
            except Exception as e:
                self.logger.error(f"Mem0客户端初始化失败: {e}")
                raise Mem0OperationError(f"无法初始化Mem0客户端: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "ltm_memories",
                    "path": "data/memories_db"
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-ada-002"
                }
            }
        }
    
    async def close(self) -> None:
        """清理资源（可选调用，用于优雅关闭）"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        self.logger.info("Mem0服务资源已清理")
    
    def _validate_input(self, data: Dict[str, Any]) -> None:
        """验证输入数据"""
        content = data.get("content", "").strip()
        if not content:
            raise ValueError("记忆内容不能为空")
            
        user_id = data.get("user_id", "").strip()
        if not user_id:
            raise ValueError("用户ID不能为空")
    
    def _extract_memory_id(self, result: Any) -> str:
        """从Mem0结果中提取记忆ID"""
        if isinstance(result, dict):
            return result.get("id", str(result))
        elif isinstance(result, str):
            return result
        else:
            return str(result)
    
    async def add_memory(self, data: Dict[str, Any]) -> str:
        """添加记忆到Mem0"""
        # 自动懒加载初始化
        await self._ensure_client()
        
        try:
            # 验证输入数据
            self._validate_input(data)
            
            content = data.get("content", "").strip()
            user_id = data.get("user_id", "").strip()
            metadata = data.get("metadata", {})
            
            # 在专用线程池中调用Mem0 API
            result = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._client.add,
                content,
                user_id,
                metadata
            )
            
            # 处理返回结果
            memory_id = self._extract_memory_id(result)
            self.logger.debug(f"成功添加记忆: {memory_id} (用户: {user_id})")
            return memory_id
            
        except (ValueError, Mem0OperationError):
            raise  # 重新抛出已知异常
        except Exception as e:
            self.logger.error(f"添加记忆失败 (用户: {data.get('user_id', 'unknown')}): {e}")
            raise Mem0OperationError(f"添加记忆失败: {e}")

    # 兼容旧调用：某些模块使用 mem0_client.add(messages=..., user_id=..., metadata=...)
    async def add(self, messages: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        return await self.add_memory({
            "content": messages,
            "user_id": user_id,
            "metadata": metadata or {}
        })
    
    async def search(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """搜索相关记忆"""
        await self._ensure_client()
        
        try:
            # 验证输入
            if not query.strip():
                raise ValueError("搜索查询不能为空")
            if not user_id.strip():
                raise ValueError("用户ID不能为空")
            if limit <= 0:
                raise ValueError("限制数量必须大于0")
            
            # 在线程池中调用Mem0 API
            results = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._client.search,
                query.strip(),
                user_id.strip(),
                limit
            )
            
            # 确保返回列表格式
            if not isinstance(results, list):
                results = [results] if results else []
                
            self.logger.debug(f"搜索到 {len(results)} 条记忆 (查询: {query[:20]}, 用户: {user_id})")
            return results
            
        except (ValueError, Mem0OperationError):
            raise
        except Exception as e:
            self.logger.error(f"搜索记忆失败 (查询: {query[:20]}, 用户: {user_id}): {e}")
            raise Mem0OperationError(f"搜索记忆失败: {e}")
    
    async def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所有记忆"""
        await self._ensure_client()
        
        try:
            # 验证输入
            if not user_id.strip():
                raise ValueError("用户ID不能为空")
            
            # 在线程池中调用Mem0 API
            results = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._client.get_all,
                user_id.strip()
            )
            
            # 确保返回列表格式
            if not isinstance(results, list):
                results = [results] if results else []
                
            self.logger.debug(f"获取到 {len(results)} 条记忆 (用户: {user_id})")
            return results
            
        except (ValueError, Mem0OperationError):
            raise
        except Exception as e:
            self.logger.error(f"获取记忆失败 (用户: {user_id}): {e}")
            raise Mem0OperationError(f"获取记忆失败: {e}")
    
    async def update(self, memory_id: str, data: Dict[str, Any]) -> Any:
        """更新记忆"""
        await self._ensure_client()
        
        try:
            # 验证输入
            if not memory_id.strip():
                raise ValueError("记忆ID不能为空")
            if not isinstance(data, dict):
                raise ValueError("更新数据必须是字典")
            
            # 在线程池中调用Mem0 API
            result = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._client.update,
                memory_id.strip(),
                data
            )
            
            self.logger.debug(f"成功更新记忆: {memory_id}")
            return result
            
        except (ValueError, Mem0OperationError):
            raise
        except Exception as e:
            self.logger.error(f"更新记忆失败 (ID: {memory_id}): {e}")
            raise Mem0OperationError(f"更新记忆失败: {e}")
    
    async def delete(self, memory_id: str) -> Any:
        """删除记忆"""
        await self._ensure_client()
        
        try:
            # 验证输入
            if not memory_id.strip():
                raise ValueError("记忆ID不能为空")
            
            # 在线程池中调用Mem0 API
            result = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._client.delete,
                memory_id.strip()
            )
            
            self.logger.debug(f"成功删除记忆: {memory_id}")
            return result
            
        except (ValueError, Mem0OperationError):
            raise
        except Exception as e:
            self.logger.error(f"删除记忆失败 (ID: {memory_id}): {e}")
            raise Mem0OperationError(f"删除记忆失败: {e}")
    
    def convert_to_user_memory(self, mem0_memory: Dict[str, Any]) -> UserMemory:
        """将Mem0记忆转换为UserMemory对象"""
        try:
            # 提取基本信息
            user_id = mem0_memory.get("user_id", "")
            content = mem0_memory.get("memory", "")
            
            # 处理元数据
            metadata_dict = mem0_memory.get("metadata", {})
            
            # 解析分类
            category_str = metadata_dict.get("category", "general")
            try:
                category = MemoryCategory(category_str.lower())
            except ValueError:
                category = MemoryCategory.GENERAL
            
            # 解析时间
            created_at_str = metadata_dict.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                except ValueError:
                    created_at = datetime.now()
            else:
                created_at = datetime.now()
            
            # 创建元数据对象
            metadata = MemoryMetadata(
                category=category,
                confidence=metadata_dict.get("confidence", 0.5),
                source=metadata_dict.get("source", "mem0"),
                tags=metadata_dict.get("tags", []),
                created_at=created_at
            )
            
            # 创建UserMemory对象
            user_memory = UserMemory(
                user_id=user_id,
                content=content,
                metadata=metadata,
                memory_id=mem0_memory.get("id")
            )
            
            return user_memory
            
        except Exception as e:
            self.logger.error(f"转换UserMemory失败: {e}")
            raise
