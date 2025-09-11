import asyncio
import json
import logging
import os
# 热重载测试注释 - 修改时间: 2025-08-19 11:14 - 最终测试
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import redis.asyncio as redis
from openai import AsyncOpenAI

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别以便更好调试
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client: Optional[redis.Redis] = None
ai_client: Optional[AsyncOpenAI] = None
config = {}
processing_tasks = {}

def load_config():
    """加载配置文件"""
    global config
    try:
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info("Configuration loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return False

class AIProcessor:
    def __init__(self):
        self.system_prompt = config.get("ai", {}).get("system_prompt", "")
        self.fallback_to_rules = config.get("ai", {}).get("fallback_to_rules", True)
        
    async def process_text(self, text: str, ltm_context: Optional[list] = None) -> str:
        """处理文本输入，返回AI回复"""
        try:
            # 首先尝试使用真实AI
            if ai_client:
                return await self._process_with_ai(text, ltm_context=ltm_context)
            elif self.fallback_to_rules:
                logger.warning("AI client not available, falling back to rules")
                return self._process_with_rules(text)
            else:
                return "AI服务暂时不可用，请稍后再试。"
                
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            if self.fallback_to_rules:
                logger.info("Falling back to rule-based responses")
                return self._process_with_rules(text)
            else:
                return "抱歉，我遇到了一些技术问题。请稍后再试！"
    
    async def _process_with_ai(self, text: str, ltm_context: Optional[list] = None) -> str:
        """使用真实AI处理文本"""
        try:
            ai_config = config.get("ai", {})
            
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            
            # 获取全局对话历史上下文（虚拟偶像共享所有记忆）
            context = await self._get_global_context()
            logger.info(f"Retrieved {len(context)} messages from global context")
            for msg in context:
                role = "user" if msg["source"] == "user" else "assistant"
                messages.append({"role": role, "content": msg["content"]})

            # 注入长期记忆检索结果（若有）
            if ltm_context:
                try:
                    snippets = []
                    for i, mem in enumerate(ltm_context[:5], start=1):
                        content = (
                            (mem.get("content") if isinstance(mem, dict) else None)
                            or (mem.get("memory") if isinstance(mem, dict) else None)
                            or str(mem)
                        )
                        if content:
                            snippets.append(f"{i}) {content}")
                    if snippets:
                        joined = "\n".join(snippets)
                        messages.append({
                            "role": "system",
                            "content": f"Relevant memories for context:\n{joined}"
                        })
                except Exception as e:
                    logger.warning(f"Failed to inject LTM context: {e}")
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": text})
            
            logger.info(f"Sending request to AI API: {text[:50]}...")
            
            response = await ai_client.chat.completions.create(
                model=ai_config.get("model", "gpt-3.5-turbo"),
                messages=messages,
                max_tokens=ai_config.get("max_tokens", 1000),
                temperature=ai_config.get("temperature", 0.7),
                timeout=ai_config.get("timeout", 30)
            )
            
            # 安全地处理响应内容
            content = response.choices[0].message.content
            if content is None:
                logger.warning("AI returned empty content, possibly due to content filtering")
                raise ValueError("AI response content is empty (likely filtered)")
            
            ai_reply = content.strip()
            if not ai_reply:
                logger.warning("AI returned empty response after stripping")
                raise ValueError("AI response is empty after processing")
            
            logger.info(f"AI response received: {ai_reply[:50]}...")
            return ai_reply
            
        except Exception as e:
            logger.error(f"AI API error: {e}")
            raise
    
    def _process_with_rules(self, text: str) -> str:
        """使用规则回复（备用方案）"""
        text_lower = text.strip().lower()
        
        # 处理敏感内容
        sensitive_keywords = ["杀", "死", "打", "暴力", "威胁"]
        if any(keyword in text_lower for keyword in sensitive_keywords):
            return "哎呀，请不要说这些不开心的话呢～我们聊点别的吧！比如今天天气怎么样？"
        
        # 简单的规则回复
        if "你好" in text_lower or "hello" in text_lower:
            return "你好！我是AI虚拟主播小艾，很高兴见到你！"
        elif "天气" in text_lower:
            return "今天天气不错呢！不过我建议你查看天气预报获取准确信息。"
        elif "唱歌" in text_lower:
            return "我很想为你唱歌，但目前还在学习中。不过我可以和你聊天！"
        elif "再见" in text_lower or "拜拜" in text_lower:
            return "再见！期待下次和你聊天，记得常来找我哦！"
        elif "谢谢" in text_lower:
            return "不用谢！能帮到你我很开心。还有什么想聊的吗？"
        elif "?" in text or "？" in text:
            clean_text = text.replace('?', '').replace('？', '').strip()
            return f"关于「{clean_text}」这个问题，让我想想... 这确实是个有趣的话题呢！"
        else:
            return f"你说「{text}」，这很有意思！作为AI主播，我正在学习如何更好地与大家交流。"
    
    async def process_audio(self, audio_file: str) -> tuple[str, Optional[str]]:
        """处理音频输入，返回文本回复和音频文件路径"""
        try:
            # 这里应该实现语音识别
            # 目前返回模拟结果
            logger.info(f"Processing audio file: {audio_file}")
            
            # 模拟语音识别结果
            recognized_text = "你好，我刚才说了一些话"
            
            # 处理识别出的文本
            response_text = await self.process_text(recognized_text)
            
            # 这里应该调用TTS生成音频回复
            # 目前返回None表示没有音频
            response_audio = None
            
            return response_text, response_audio
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return "抱歉，音频处理出现问题。", None
    
    async def _get_global_context(self) -> list:
        """从记忆模块获取全局上下文（虚拟偶像的完整记忆）"""
        try:
            context_key = "memory:global_context"
            
            if redis_client:
                # 获取最近的全局消息
                messages_json = await redis_client.lrange(context_key, -20, -1)
                context = []
                for msg_json in messages_json:
                    try:
                        message = json.loads(msg_json)
                        context.append(message)
                    except json.JSONDecodeError:
                        continue
                return context
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting global context: {e}")
            return []

class TaskProcessor:
    def __init__(self):
        self.ai_processor = AIProcessor()
        
    async def process_memory_update(self, event_data: dict):
        """处理记忆更新事件"""
        try:
            user_id = event_data.get("user_id", "anonymous")
            message_id = event_data.get("message_id")
            source = event_data.get("source")
            
            logger.info(f"Processing memory update for user {user_id}, message {message_id}")
            
            # 验证事件数据
            if source != "user":
                logger.warning(f"Ignoring non-user message: {source}")
                return
            
            # 从全局记忆获取消息内容（带重试机制）
            # input_text = await self._get_message_content_with_retry(message_id)
            input_text = event_data.get("content")
            if not input_text:
                logger.error(f"Could not retrieve content for message {message_id}")
                return
            
            # 如启用LTM，检索相关记忆用于增强提示词
            ltm_context = await fetch_ltm_context(user_id, input_text)

            # AI处理（结合全局记忆 + LTM检索）
            response_text = await self.ai_processor.process_text(input_text, ltm_context=ltm_context)
            
            # 发布AI响应到记忆模块
            await self._publish_ai_response(user_id, response_text, message_id)
            
            # 同时发送到输出模块，使用接收到的原始 task_id
            original_task_id = event_data.get("task_id")
            if original_task_id:
                asyncio.create_task(self._request_tts_synthesis(response_text, message_id, original_task_id))
                # await self._send_response(original_task_id, response_text, None) # 已禁用：由TTS服务统一发送最终响应
            else:
                # 如果没有原始task_id，使用旧的方法作为fallback
                task_id = f"{user_id}_{int(asyncio.get_event_loop().time() * 1000)}"
                await self._send_response(task_id, response_text, None)
            
        except Exception as e:
            logger.error(f"Error processing memory update: {e}")
    
    # async def _get_message_content_with_retry(self, message_id: str, max_retries: int = 3) -> str:
    #     """带重试机制的消息内容获取"""
    #     for attempt in range(max_retries):
    #         try:
    #             if not redis_client:
    #                 logger.error("Redis client not available")
    #                 return ""
                
    #             # 从全局记忆中查找指定消息ID
    #             context_key = "memory:global_context"
    #             messages_json = await redis_client.lrange(context_key, -50, -1)  # 获取最近50条消息
                
    #             for msg_json in reversed(messages_json):  # 从最新的开始查找
    #                 try:
    #                     message = json.loads(msg_json)
    #                     if message.get("message_id") == message_id:
    #                         content = message.get("content", "")
    #                         if content.strip():
    #                             logger.info(f"Found message {message_id} on attempt {attempt + 1}")
    #                             return content
    #                 except json.JSONDecodeError:
    #                     continue
                
    #             # 如果没找到，等待一小段时间后重试
    #             if attempt < max_retries - 1:
    #                 await asyncio.sleep(0.1 * (attempt + 1))  # 递增等待时间
                    
    #         except Exception as e:
    #             logger.error(f"Error retrieving message {message_id} on attempt {attempt + 1}: {e}")
    #             if attempt < max_retries - 1:
    #                 await asyncio.sleep(0.1 * (attempt + 1))
        
    #     logger.warning(f"Failed to retrieve message {message_id} after {max_retries} attempts")
    #     return ""
    
    async def _publish_ai_response(self, user_id: str, response_text: str, original_message_id: str):
        """发布AI响应到记忆模块"""
        try:
            if not redis_client:
                logger.error("Redis client not available")
                return
            
            response_data = {
                "user_id": user_id,
                "text": response_text,
                "original_message_id": original_message_id,
                "timestamp": asyncio.get_running_loop().time()
            }
            
            # 发布到AI响应频道，供记忆模块监听
            await redis_client.publish("ai_responses", json.dumps(response_data))
            
            logger.info(f"Published AI response for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error publishing AI response: {e}")
    
    async def _process_text_task(self, task_id: str, input_file: str):
        """处理文本任务"""
        try:
            # 读取输入文本
            with open(input_file, "r", encoding="utf-8") as f:
                input_text = f.read().strip()
            
            logger.info(f"Input text: {input_text[:100]}...")
            
            # AI处理（使用全局记忆）
            response_text = await self.ai_processor.process_text(input_text)
            
            # 发送响应
            await self._send_response(task_id, response_text, None)
            
        except Exception as e:
            logger.error(f"Error in text task {task_id}: {e}")
            await self._send_error_response(task_id, str(e))
    
    async def _process_audio_task(self, task_id: str, input_file: str):
        """处理音频任务"""
        try:
            # AI处理音频
            response_text, response_audio = await self.ai_processor.process_audio(input_file)
            
            # 发送响应
            await self._send_response(task_id, response_text, response_audio)
            
        except Exception as e:
            logger.error(f"Error in audio task {task_id}: {e}")
            await self._send_error_response(task_id, str(e))
    
    async def _send_response(self, task_id: str, text: str, audio_file: Optional[str]):
        """发送处理结果到Redis响应频道"""
        if not redis_client:
            logger.error("Redis client not available")
            return
            
        try:
            # 根据配置添加延迟
            delay = config.get("processing", {}).get("response_delay", 0.1)
            await asyncio.sleep(delay)
            
            response = {
                "text": text,
            }
            
            if audio_file:
                response["audio_file"] = audio_file
            
            # 发送到特定任务的响应频道
            channel = f"task_response:{task_id}"
            await redis_client.publish(channel, json.dumps(response))
            
            logger.info(f"Sent response for task {task_id} to channel {channel}")
            processing_tasks[task_id] = "completed"
            
        except Exception as e:
            logger.error(f"Error sending response for task {task_id}: {e}")

    async def _request_tts_synthesis(self, text: str, message_id: str, task_id: str):
        """将文本发送到TTS请求队列"""
        if not redis_client:
            logger.error("Redis client not available for TTS request")
            return
        
        try:
            # 从配置中获取TTS请求队列的名称
            tts_queue_name = config.get("tts", {}).get("request_queue", "tts_requests")

            # 构建TTS请求消息
            tts_request = {
                "message_id": message_id,
                "task_id": task_id, #将task_id作为参数传递给TTS服务
                "text": text,
                "response_channel": f"task_response:{task_id}" # 明确告诉TTS服务将结果发到哪里
            }

            # 使用 LPUSH 将请求推入队列
            await redis_client.lpush(tts_queue_name, json.dumps(tts_request))
            logger.info(f"Sent TTS request for task {task_id} to queue {tts_queue_name}")

        except Exception as e:
            logger.error(f"Error sending TTS request for task {task_id}: {e}")
    
    async def _send_error_response(self, task_id: str, error_message: str):
        """发送错误响应"""
        if not redis_client:
            return
            
        try:
            # 根据配置添加延迟
            delay = config.get("processing", {}).get("response_delay", 0.1)
            await asyncio.sleep(delay)
            
            response = {
                "text": f"处理出错: {error_message}",
                "error": True
            }
            
            channel = f"task_response:{task_id}"
            await redis_client.publish(channel, json.dumps(response))
            
            logger.error(f"Sent error response for task {task_id}: {error_message}")
            processing_tasks[task_id] = "error"
            
        except Exception as e:
            logger.error(f"Error sending error response: {e}")

async def init_redis():
    """初始化Redis连接，优先从环境变量读取配置"""
    global redis_client
    try:
        # 优先从环境变量获取Redis配置
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))

        # 如果环境变量没有，再尝试从config.json读取
        if redis_host == "localhost":
            redis_config = config.get("redis", {})
            redis_host = redis_config.get("host", redis_host)
            redis_port = redis_config.get("port", redis_port)

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        await redis_client.ping()
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        redis_client = None

async def init_ai():
    global ai_client
    try:
        ai_config = config.get("ai", {})
        # 优先从环境变量读取API key，如果没有再从配置文件读取
        api_key = os.getenv("OPENAI_API_KEY") or ai_config.get("api_key")
        api_base = ai_config.get("api_base")
        
        if not api_key or api_key == "your-api-key-here":
            logger.warning("AI API key not configured (set OPENAI_API_KEY environment variable), will use fallback rules only")
            return
        
        ai_client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=ai_config.get("timeout", 30),
            max_retries=ai_config.get("max_retries", 3)
        )
        
        # 测试连接
        logger.info("Testing AI API connection...")
        test_response = await ai_client.chat.completions.create(
            model=ai_config.get("model", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": "测试"}],
            max_tokens=10
        )
        
        logger.info("AI API connection successful")
        
    except Exception as e:
        logger.error(f"Failed to initialize AI client: {e}")
        logger.info("Will use fallback rules instead")
        ai_client = None

async def cleanup():
    if redis_client:
        await redis_client.close()
    if ai_client:
        await ai_client.close()
    logger.info("AI Processor shutdown")

async def fetch_ltm_context(user_id: str, query: str) -> list:
    """向长期记忆服务请求相关记忆，超时则返回空列表（模块级帮助函数）"""
    try:
        if not redis_client:
            return []

        enable = os.getenv("ENABLE_LTM", "false").lower() in {"1", "true", "yes", "on"}
        if not enable:
            return []

        import uuid

        queue = os.getenv("LTM_REQUESTS_QUEUE", "ltm_requests")
        resp_channel = os.getenv("LTM_RESPONSES_CHANNEL", "ltm_responses")
        timeout_ms = int(os.getenv("LTM_SEARCH_TIMEOUT_MS", "600"))

        request_id = f"req-{uuid.uuid4()}"
        req = {
            "request_id": request_id,
            "type": "search",
            "user_id": user_id,
            "data": {"query": query, "limit": 5}
        }

        # 发送请求
        await redis_client.lpush(queue, json.dumps(req, ensure_ascii=False))

        # 等待响应（短时订阅 + 相关性过滤）
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(resp_channel)

        try:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + (timeout_ms / 1000.0)
            while loop.time() < deadline:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.05)
                if not msg:
                    await asyncio.sleep(0.02)
                    continue
                if msg.get("type") != "message":
                    continue
                try:
                    payload = json.loads(msg.get("data"))
                    if payload.get("request_id") == request_id and payload.get("user_id") == user_id:
                        if payload.get("success", False):
                            return payload.get("memories", []) or []
                        return []
                except Exception:
                    continue
        finally:
            try:
                await pubsub.unsubscribe(resp_channel)
            except Exception:
                pass
            try:
                await pubsub.close()
            except Exception:
                pass

        # 超时
        return []
    except Exception as e:
        logger.warning(f"LTM context fetch failed: {e}")
        return []

async def memory_update_listener():
    """监听记忆更新事件"""
    if not redis_client:
        logger.error("Redis client not available")
        return
        
    processor = TaskProcessor()
    memory_channel = "memory_updates"
    
    logger.info(f"Starting memory update listener for {memory_channel}")
    
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(memory_channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event_data = json.loads(message["data"])
                    # 只处理需要AI响应的事件
                    if event_data.get("require_ai_response", False) and event_data.get("source") == "user":
                        logger.info(f"Received memory update event: {event_data}")
                        # 异步处理记忆更新事件
                        asyncio.create_task(processor.process_memory_update(event_data))
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in memory update: {e}")
                except Exception as e:
                    logger.error(f"Error in memory update listener: {e}")
                    await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("memory_update_listener cancelled; cleaning up pubsub")
        raise
    finally:
        try:
            await pubsub.unsubscribe(memory_channel)
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass

async def main():
    """主函数"""
    logger.info("Starting AI Chat Processor...")
    
    # 加载配置
    if not load_config():
        logger.error("Failed to load configuration, exiting")
        return
    
    # 初始化Redis
    await init_redis()
    
    if not redis_client:
        logger.error("Cannot start without Redis connection")
        return
    
    # 初始化AI客户端
    await init_ai()
    
    try:
        # 启动记忆更新监听器
        await memory_update_listener()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await cleanup()

if __name__ == "__main__":
    asyncio.run(main())
