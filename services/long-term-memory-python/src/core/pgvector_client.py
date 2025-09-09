"""
pgvector向量数据库客户端

提供向量存储、检索和管理功能，支持：
- 向量存储和相似度搜索
- 用户数据隔离
- 批量操作
- 连接管理和错误处理
"""

import asyncio
import asyncpg
import logging
from typing import List, Dict, Any, Optional, Union
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from src.models.memory import UserMemory


class PgvectorOperationError(Exception):
    """pgvector操作错误"""
    pass


class PgvectorClient:
    """pgvector向量数据库客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化pgvector客户端
        
        Args:
            config: 数据库配置
                - host: PostgreSQL主机
                - port: 端口
                - database: 数据库名
                - user: 用户名
                - password: 密码
                - table_name: 向量表名
        """
        self.config = config
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "long_term_memory")
        self.user = config.get("user", "ltm_user")
        self.password = config.get("password", "ltm_password")
        self.table_name = config.get("table_name", "memory_vectors")
        
        self._pool: Optional[asyncpg.Pool] = None
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pgvector")
        self.logger = logging.getLogger(__name__)
        
        # 向量维度常量
        self.VECTOR_DIMENSION = 1536
        
        # 性能统计
        self._query_count = 0
        self._error_count = 0

    async def connect(self) -> None:
        """建立数据库连接池 - 优化连接参数"""
        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                min_size=2,
                max_size=20,  # 增加最大连接数
                max_queries=50000,  # 每连接最大查询数
                max_inactive_connection_lifetime=300,  # 5分钟空闲超时
                command_timeout=60,  # 增加命令超时
                setup=self._setup_connection  # 连接初始化回调
            )
            
            # 创建表和索引（如果不存在）
            await self._ensure_table_exists()
            
            self.logger.info(f"pgvector连接池建立成功: {self.host}:{self.port}")
            
        except Exception as e:
            self.logger.error(f"pgvector连接失败: {e}")
            raise PgvectorOperationError(f"连接数据库失败: {e}")

    async def disconnect(self) -> None:
        """关闭数据库连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self.logger.info("pgvector连接池已关闭")
            
        if self._executor:
            self._executor.shutdown(wait=True)

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._pool is not None and not self._pool._closed

    async def _setup_connection(self, conn) -> None:
        """连接初始化回调 - 设置连接参数优化性能"""
        try:
            # 设置连接级别的优化参数
            await conn.execute("SET work_mem = '256MB'")  # 增加工作内存
            await conn.execute("SET effective_cache_size = '4GB'")  # 设置缓存大小
            await conn.execute("SET random_page_cost = 1.1")  # 优化SSD随机访问
            await conn.execute("SET seq_page_cost = 1.0")  # 序列访问成本
            await conn.execute("SET cpu_tuple_cost = 0.01")  # CPU元组处理成本
            await conn.execute("SET maintenance_work_mem = '512MB'")  # 维护操作内存
            
            self.logger.debug("连接性能参数设置完成")
        except Exception as e:
            self.logger.warning(f"设置连接参数失败: {e}")

    async def _ensure_connection(self) -> None:
        """确保连接存在（懒加载）"""
        if not self.is_connected():
            await self.connect()

    async def _ensure_table_exists(self) -> None:
        """确保向量表和索引存在"""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id VARCHAR(255) PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            category VARCHAR(100),
            embedding vector({self.VECTOR_DIMENSION}) NOT NULL,
            metadata JSONB DEFAULT '{{}}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        create_index_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_user_embedding 
        ON {self.table_name} USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100);
        """
        
        create_user_index_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_user_id 
        ON {self.table_name} (user_id);
        """
        
        async with self._pool.acquire() as conn:
            # 启用pgvector扩展
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # 创建表
            await conn.execute(create_table_sql)
            
            # 创建索引
            await conn.execute(create_index_sql)
            await conn.execute(create_user_index_sql)

    def _validate_vector(self, embedding: List[float]) -> None:
        """验证向量格式"""
        if not isinstance(embedding, list):
            raise ValueError("embedding必须是列表类型")
        
        if len(embedding) != self.VECTOR_DIMENSION:
            raise ValueError(f"向量维度必须为{self.VECTOR_DIMENSION}")
        
        if not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError("向量元素必须为数字")

    def _validate_user_id(self, user_id: str) -> None:
        """验证用户ID"""
        if not user_id or not user_id.strip():
            raise ValueError("用户ID不能为空")

    def _validate_threshold(self, threshold: float) -> None:
        """验证相似度阈值"""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("相似度阈值必须在0-1之间")

    async def insert_memory(self, memory_data: Dict[str, Any]) -> str:
        """
        插入记忆向量
        
        Args:
            memory_data: 记忆数据
                - id: 记忆ID
                - embedding: 向量 (1536维)
                - content: 内容
                - user_id: 用户ID
                - category: 分类
                - metadata: 元数据
                
        Returns:
            str: 插入成功的记忆ID
        """
        await self._ensure_connection()
        
        # 数据验证
        memory_id = memory_data.get("id")
        embedding = memory_data.get("embedding")
        content = memory_data.get("content")
        user_id = memory_data.get("user_id")
        category = memory_data.get("category", "general")
        metadata = memory_data.get("metadata", {})
        
        if not memory_id:
            raise ValueError("记忆ID不能为空")
        
        self._validate_vector(embedding)
        self._validate_user_id(user_id)
        
        if not content:
            raise ValueError("记忆内容不能为空")
        
        try:
            insert_sql = f"""
            INSERT INTO {self.table_name} 
            (id, user_id, content, category, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                category = EXCLUDED.category,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
            """
            
            async with self._pool.acquire() as conn:
                result = await conn.fetchval(
                    insert_sql,
                    memory_id, user_id, content, category, embedding, metadata
                )
                
            self.logger.debug(f"成功插入记忆: {memory_id} (用户: {user_id})")
            return result
            
        except Exception as e:
            self.logger.error(f"插入记忆失败: {e}")
            raise PgvectorOperationError(f"插入记忆失败: {e}")

    async def search_similar(
        self, 
        query_vector: List[float], 
        user_id: str,
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量 (1536维)
            user_id: 用户ID
            limit: 返回结果数量
            threshold: 相似度阈值 (0-1)
            
        Returns:
            List[Dict]: 搜索结果列表
        """
        await self._ensure_connection()
        
        # 参数验证
        self._validate_vector(query_vector)
        self._validate_user_id(user_id)
        self._validate_threshold(threshold)
        
        try:
            search_sql = f"""
            SELECT 
                id, content, user_id, category, metadata,
                1 - (embedding <=> $1) as similarity,
                created_at, updated_at
            FROM {self.table_name}
            WHERE user_id = $2 
                AND 1 - (embedding <=> $1) >= $3
            ORDER BY embedding <=> $1
            LIMIT $4;
            """
            
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    search_sql,
                    query_vector, user_id, threshold, limit
                )
                
            results = []
            for row in rows:
                result = {
                    "id": row["id"],
                    "content": row["content"],
                    "user_id": row["user_id"],
                    "category": row["category"],
                    "similarity": float(row["similarity"]),
                    "metadata": dict(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                results.append(result)
            
            self.logger.debug(f"相似度搜索完成: {len(results)}个结果 (用户: {user_id})")
            return results
            
        except Exception as e:
            self.logger.error(f"相似度搜索失败: {e}")
            raise PgvectorOperationError(f"相似度搜索失败: {e}")

    async def get_memory_by_id(self, memory_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取记忆
        
        Args:
            memory_id: 记忆ID
            user_id: 用户ID（用于权限验证）
            
        Returns:
            Optional[Dict]: 记忆数据或None
        """
        await self._ensure_connection()
        
        self._validate_user_id(user_id)
        
        try:
            select_sql = f"""
            SELECT id, content, user_id, category, embedding, metadata, created_at, updated_at
            FROM {self.table_name}
            WHERE id = $1 AND user_id = $2;
            """
            
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(select_sql, memory_id, user_id)
                
            if row:
                return {
                    "id": row["id"],
                    "content": row["content"],
                    "user_id": row["user_id"],
                    "category": row["category"],
                    "embedding": list(row["embedding"]),  # 转换向量为列表
                    "metadata": dict(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取记忆失败: {e}")
            raise PgvectorOperationError(f"获取记忆失败: {e}")

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            user_id: 用户ID（用于权限验证）
            
        Returns:
            bool: 删除是否成功
        """
        await self._ensure_connection()
        
        self._validate_user_id(user_id)
        
        try:
            delete_sql = f"""
            DELETE FROM {self.table_name}
            WHERE id = $1 AND user_id = $2;
            """
            
            async with self._pool.acquire() as conn:
                result = await conn.execute(delete_sql, memory_id, user_id)
                
            # 检查影响的行数
            affected_rows = int(result.split()[-1])
            success = affected_rows > 0
            
            if success:
                self.logger.debug(f"成功删除记忆: {memory_id} (用户: {user_id})")
            else:
                self.logger.warning(f"记忆不存在或无权限删除: {memory_id} (用户: {user_id})")
                
            return success
            
        except Exception as e:
            self.logger.error(f"删除记忆失败: {e}")
            raise PgvectorOperationError(f"删除记忆失败: {e}")

    async def bulk_insert(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量插入记忆 - 使用事务优化性能
        
        Args:
            memories: 记忆数据列表
            
        Returns:
            List[Dict]: 插入结果列表
        """
        await self._ensure_connection()
        
        if not memories:
            return []
        
        results = []
        
        try:
            async with self._pool.acquire() as conn:
                # 使用事务批量插入
                async with conn.transaction():
                    insert_sql = f"""
                    INSERT INTO {self.table_name} 
                    (id, user_id, content, category, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        category = EXCLUDED.category,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id;
                    """
                    
                    # 批量执行插入
                    for i, memory_data in enumerate(memories):
                        result = {
                            "id": memory_data.get("id", f"batch_{i}"),
                            "success": False,
                            "error": None,
                            "memory_id": None
                        }
                        
                        try:
                            # 验证数据
                            self._validate_memory_data(memory_data)
                            
                            # 执行插入
                            memory_id = await conn.fetchval(
                                insert_sql,
                                memory_data["id"],
                                memory_data["user_id"],
                                memory_data["content"],
                                memory_data.get("category", "general"),
                                memory_data["embedding"],
                                memory_data.get("metadata", {})
                            )
                            
                            result["success"] = True
                            result["memory_id"] = memory_id
                            
                        except Exception as e:
                            result["error"] = str(e)
                            self.logger.error(f"批量插入第{i+1}项失败: {e}")
                            # 对于数据验证错误，继续处理其他项
                            if "验证" in str(e):
                                continue
                            # 对于数据库错误，回滚整个事务
                            raise
                            
                        results.append(result)
                        
        except Exception as e:
            self.logger.error(f"批量插入事务失败: {e}")
            # 如果事务失败，标记所有未处理的项为失败
            for i in range(len(results), len(memories)):
                results.append({
                    "id": memories[i].get("id", f"batch_{i}"),
                    "success": False,
                    "error": f"事务失败: {str(e)}",
                    "memory_id": None
                })
        
        successful_count = sum(1 for r in results if r["success"])
        self.logger.info(f"批量插入完成: {successful_count}/{len(memories)} 成功")
        
        return results

    def _validate_memory_data(self, memory_data: Dict[str, Any]) -> None:
        """
        验证记忆数据完整性
        
        Args:
            memory_data: 待验证的记忆数据
        """
        required_fields = ["id", "user_id", "content", "embedding"]
        for field in required_fields:
            if field not in memory_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        self._validate_vector(memory_data["embedding"])
        self._validate_user_id(memory_data["user_id"])
        
        if not memory_data["content"].strip():
            raise ValueError("记忆内容不能为空")

    async def convert_to_user_memory(self, memory_data: Dict[str, Any]) -> UserMemory:
        """
        转换为UserMemory对象
        
        Args:
            memory_data: 原始记忆数据
            
        Returns:
            UserMemory: 转换后的对象
        """
        try:
            from src.models.memory import MemoryMetadata, MemoryCategory
            
            # 转换metadata
            raw_metadata = memory_data.get("metadata", {})
            category_str = memory_data.get("category", "preference")
            
            # 映射字符串到MemoryCategory枚举
            try:
                category = MemoryCategory(category_str)
            except ValueError:
                category = MemoryCategory.PREFERENCE
            
            # 创建MemoryMetadata对象
            metadata = MemoryMetadata(
                category=category,
                confidence=raw_metadata.get("confidence", 0.8),
                source=raw_metadata.get("source", "conversation"),
                tags=raw_metadata.get("tags", [])
            )
            
            # 创建UserMemory对象
            user_memory = UserMemory(
                id=memory_data.get("id"),
                user_id=memory_data["user_id"],
                content=memory_data["content"],
                metadata=metadata
            )
            
            # 保留向量信息
            if "embedding" in memory_data:
                user_memory.embedding = memory_data["embedding"]
                
            return user_memory
            
        except Exception as e:
            self.logger.error(f"转换UserMemory对象失败: {e}")
            raise PgvectorOperationError(f"转换UserMemory对象失败: {e}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()