import asyncio
import json
import logging
from typing import Optional, Dict, List, Any
import aiohttp
import time

logger = logging.getLogger(__name__)

class LettaAPIError(Exception):
    """Letta API相关错误"""
    pass

class LettaClient:
    """Letta API客户端"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()
    
    async def _ensure_session(self):
        """确保aiohttp会话存在"""
        if self.session is None or self.session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=headers
            )
    
    async def close(self):
        """关闭客户端会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """发送HTTP请求"""
        await self._ensure_session()
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                
                async with self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            return json.loads(response_text)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse JSON response: {e}")
                            logger.debug(f"Raw response: {response_text}")
                            raise LettaAPIError(f"Invalid JSON response from Letta API")
                    
                    elif response.status in [500, 502, 503, 504]:
                        # 服务器错误，可以重试
                        logger.warning(f"Server error {response.status} on attempt {attempt + 1}: {response_text}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # 指数退避
                            continue
                    
                    # 其他错误不重试
                    logger.error(f"API request failed with status {response.status}: {response_text}")
                    raise LettaAPIError(f"API request failed: {response.status} - {response_text}")
                    
            except aiohttp.ClientError as e:
                logger.error(f"Network error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise LettaAPIError(f"Network error after {self.max_retries} attempts: {e}")
        
        raise LettaAPIError(f"Failed after {self.max_retries} attempts")
    
    async def health_check(self) -> bool:
        """检查Letta API健康状态"""
        try:
            # 尝试获取可用模型
            await self._make_request("GET", "/v1/models/")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """获取所有agents列表"""
        try:
            response = await self._make_request("GET", "/v1/agents/")
            # Letta API可能直接返回列表，而不是包装在字典中
            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                return response.get("agents", [])
            else:
                logger.warning(f"Unexpected response format from list_agents: {type(response)}")
                return []
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            raise LettaAPIError(f"Failed to list agents: {e}")
    
    async def create_agent(self, name: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """创建新的agent"""
        try:
            payload = {
                "name": name,
                "llm_config": {
                    "model": "gpt-4", 
                    "model_endpoint_type": "openai",
                    "context_window": 8192
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            logger.info(f"Creating agent with name: {name}")
            response = await self._make_request("POST", "/v1/agents/", data=payload)
            
            agent_id = response.get("id")
            if not agent_id:
                raise LettaAPIError("Agent creation response missing 'id' field")
            
            logger.info(f"Successfully created agent: {agent_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to create agent '{name}': {e}")
            raise LettaAPIError(f"Failed to create agent: {e}")
    
    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取特定agent信息"""
        try:
            response = await self._make_request("GET", f"/v1/agents/{agent_id}/")
            return response
        except LettaAPIError as e:
            if "404" in str(e):
                return None
            raise
    
    async def send_message(self, agent_id: str, message: str, role: str = "user") -> Dict[str, Any]:
        """向agent发送消息"""
        try:
            payload = {
                "message": message,
                "role": role,
                "stream": False
            }
            
            logger.debug(f"Sending message to agent {agent_id}: {message[:100]}...")
            
            response = await self._make_request(
                "POST", 
                f"/v1/agents/{agent_id}/messages/", 
                data=payload
            )
            
            logger.debug(f"Received response from agent {agent_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send message to agent {agent_id}: {e}")
            raise LettaAPIError(f"Failed to send message: {e}")
    
    async def get_agent_messages(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取agent的消息历史"""
        try:
            params = {"limit": limit}
            response = await self._make_request(
                "GET", 
                f"/v1/agents/{agent_id}/messages/", 
                params=params
            )
            
            return response.get("messages", [])
            
        except Exception as e:
            logger.error(f"Failed to get messages for agent {agent_id}: {e}")
            raise LettaAPIError(f"Failed to get agent messages: {e}")
    
    async def delete_agent(self, agent_id: str) -> bool:
        """删除agent"""
        try:
            await self._make_request("DELETE", f"/v1/agents/{agent_id}/")
            logger.info(f"Successfully deleted agent: {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete agent {agent_id}: {e}")
            return False


class LettaClientPool:
    """Letta客户端连接池"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, pool_size: int = 5, **client_kwargs):
        self.base_url = base_url
        self.api_key = api_key
        self.pool_size = pool_size
        self.client_kwargs = client_kwargs
        self._pool: asyncio.Queue[LettaClient] = asyncio.Queue(maxsize=pool_size)
        self._created_clients = 0
        self._lock = asyncio.Lock()
    
    async def _create_client(self) -> LettaClient:
        """创建新的客户端"""
        client = LettaClient(
            base_url=self.base_url,
            api_key=self.api_key,
            **self.client_kwargs
        )
        await client._ensure_session()
        return client
    
    async def get_client(self) -> LettaClient:
        """从连接池获取客户端"""
        try:
            # 尝试从池中获取现有客户端
            client = self._pool.get_nowait()
            return client
        except asyncio.QueueEmpty:
            # 池为空，创建新客户端
            async with self._lock:
                if self._created_clients < self.pool_size:
                    client = await self._create_client()
                    self._created_clients += 1
                    return client
                else:
                    # 达到最大连接数，等待
                    return await self._pool.get()
    
    async def return_client(self, client: LettaClient):
        """将客户端返回连接池"""
        if not client.session.closed:
            try:
                self._pool.put_nowait(client)
            except asyncio.QueueFull:
                # 池已满，关闭客户端
                await client.close()
        else:
            # 客户端已关闭，减少计数
            async with self._lock:
                self._created_clients = max(0, self._created_clients - 1)
    
    async def close_all(self):
        """关闭所有客户端"""
        clients_to_close = []
        
        # 收集所有客户端
        while not self._pool.empty():
            try:
                client = self._pool.get_nowait()
                clients_to_close.append(client)
            except asyncio.QueueEmpty:
                break
        
        # 关闭所有客户端
        for client in clients_to_close:
            await client.close()
        
        async with self._lock:
            self._created_clients = 0