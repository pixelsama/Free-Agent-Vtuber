import asyncio
import json
import base64
import time
import uuid
from typing import Dict, Any
from pathlib import Path 

from src.core.config_manager import ConfigManager
from src.utils import RedisClient, setup_logger
from src.services.providers import ProviderFactory
from src.services.providers.openai_tts import OpenAITTS  # Import to register
from src.services.providers.edge_tts import EdgeTTS  # Import to register

class TTSService:
    """
    The main TTS service class that handles requests and orchestrates providers.
    """

    def __init__(self, config_path: str):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_config()
        self.logger = setup_logger(self.config)
        self.redis_client = RedisClient(self.config["redis"])
        self.default_provider_name = self.config["tts"]["default_provider"]
        self._running = False

    async def start(self):
        """
        Starts the TTS service and begins listening for requests.
        """
        self.logger.info("Starting TTS Service...")
        self._running = True
        self.task = asyncio.create_task(self._listen_for_requests())
        self.logger.info("TTS Service started.")

    async def stop(self):
        """
        Stops the TTS service gracefully.
        """
        self.logger.info("Stopping TTS Service...")
        self._running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.redis_client.close()
        self.logger.info("TTS Service stopped.")

    async def _listen_for_requests(self):
        request_queue = self.config["tts"]["request_queue"]
        while self._running:
            try:
                # Blocking pop with a timeout to allow for graceful shutdown
                message = await self.redis_client.blpop([request_queue], timeout=1)
                if message:
                    _, request_data = message
                    asyncio.create_task(self.process_tts_request(json.loads(request_data)))
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.handle_error(e, {})

    async def process_tts_request(self, message: Dict[str, Any]):
        """
        Processes a single TTS request.
        """
        start_time = time.time()
        message_id = message.get("message_id", str(uuid.uuid4()))
        text = message.get("text")
        
        if not text:
            await self.handle_error(ValueError("Missing 'text' in request"), message)
            return

        provider_name = message.get("provider", self.default_provider_name)
        
        try:
            audio_data, final_provider = await self._synthesize_with_fallback(text, provider_name, message.get("voice_params", {}))
            
            # 1. 创建临时文件路径
            task_id = message.get("task_id", str(uuid.uuid4()))
            temp_dir = Path(self.config.get("storage", {}).get("temp_dir", "/tmp/aivtuber_tasks"))
            task_dir = temp_dir / task_id
            task_dir.mkdir(exist_ok=True, parents=True)
            # 注意：output-handler默认寻找.wav文件，这里需要保证格式一致或进行转换
            audio_file_path = task_dir / "output.mp3" 

            # 2. 将音频数据写入文件
            with open(audio_file_path, "wb") as f:
                f.write(audio_data)
            self.logger.info(f"Saved synthesized audio to {audio_file_path}")

            # 3. 构建包含文件路径的响应
            response = {
                "message_id": message_id,
                "task_id": task_id,
                "status": "success",
                "text": message.get("text"), # 将文本也一并返回
                "audio_file": str(audio_file_path), # 返回的是文件路径！
                "metadata": {
                    "provider": final_provider,
                    "processing_time": time.time() - start_time
                }
            }
            
            # 优先使用请求中指定的响应频道，否则根据task_id构建
            response_channel = message.get("response_channel")
            if not response_channel:
                prefix = self.config["tts"].get("response_channel_prefix", "task_response:")
                task_id_for_channel = message.get("task_id")
                if task_id_for_channel:
                    response_channel = f"{prefix}{task_id_for_channel}"
                else:
                    self.logger.error(f"Cannot determine response channel for message_id: {message_id}. No 'response_channel' or 'task_id' found in request.")
                    return

            await self.redis_client.publish(response_channel, json.dumps(response))
            self.logger.info(f"Published TTS response to channel: {response_channel}")

        except Exception as e:
            await self.handle_error(e, message, provider_name)

    async def _synthesize_with_fallback(self, text: str, primary_provider: str, voice_params: dict):
        """
        Tries to synthesize with the primary provider, and falls back to others on failure.
        """
        providers_to_try = [primary_provider]
        # Simple fallback: try other available providers if the primary one fails
        available_providers = ProviderFactory.get_available_providers()
        for p in available_providers:
            if p not in providers_to_try:
                providers_to_try.append(p)

        last_exception = None
        for provider_name in providers_to_try:
            try:
                self.logger.info(f"Attempting synthesis with provider: {provider_name}")
                provider_config = self.config_manager.get_provider_config(provider_name)
                provider = ProviderFactory.create_provider(provider_name, provider_config)
                
                # Retry logic
                max_attempts = self.config["tts"].get("retry_attempts", 3)
                retry_delay = self.config["tts"].get("retry_delay", 1.0)
                
                for attempt in range(max_attempts):
                    try:
                        audio_data = await provider.synthesize(text, **voice_params)
                        self.logger.info(f"Synthesis successful with {provider_name} on attempt {attempt + 1}")
                        return audio_data, provider_name
                    except Exception as e:
                        self.logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed for provider {provider_name}: {e}")
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(retry_delay * (2 ** attempt)) # Exponential backoff
                        else:
                            raise e # Re-raise after last attempt
            except Exception as e:
                self.logger.error(f"Provider {provider_name} failed permanently: {e}")
                last_exception = e
                continue # Try next provider
        
        # If all providers fail
        raise RuntimeError(f"All TTS providers failed. Last error: {last_exception}") from last_exception

    async def handle_error(self, error: Exception, context: Dict[str, Any], provider_name: str = None):
        """
        Handles errors during processing and sends an error message.
        """
        self.logger.error(f"Error processing request: {error}", exc_info=True)
        
        error_code = "TTS_SYNTHESIS_FAILED"
        if isinstance(error, ValueError):
            error_code = "INVALID_REQUEST"
        elif isinstance(error, RuntimeError):
            error_code = "ALL_PROVIDERS_FAILED"

        error_message = {
            "message_id": context.get("message_id", str(uuid.uuid4())),
            "timestamp": time.time(),
            "status": "error",
            "error": {
                "code": error_code,
                "message": str(error),
                "details": repr(error),
                "provider": provider_name or context.get("provider", self.default_provider_name)
            }
        }
        error_channel = self.config["tts"]["error_channel"]
        await self.redis_client.publish(error_channel, json.dumps(error_message))
