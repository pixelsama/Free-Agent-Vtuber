import pytest
import json
from unittest.mock import AsyncMock, Mock, patch, mock_open

from main import TaskProcessor


class TestTaskProcessor:
    """任务处理器单元测试"""
    
    @pytest.mark.asyncio
    async def test_process_memory_update_success(self, task_processor, mock_redis):
        """测试记忆更新处理 - 成功情况"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        # 创建模拟的AI处理器
        task_processor.ai_processor = AsyncMock()
        task_processor.ai_processor.process_text = AsyncMock(return_value="模拟的AI回复")
        
        event_data = {
            "user_id": "test_user",
            "message_id": "msg_123",
            "source": "user",
            "content": "你好",
            "task_id": "task_123"
        }
        
        await task_processor.process_memory_update(event_data)
        
        # 验证AI处理器被调用
        task_processor.ai_processor.process_text.assert_called_once_with("你好")
        
        # 验证Redis发布被调用
        assert mock_redis.publish.call_count >= 1
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_process_memory_update_non_user_source(self, task_processor, mock_redis):
        """测试记忆更新处理 - 非用户消息源"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        event_data = {
            "user_id": "test_user",
            "message_id": "msg_123",
            "source": "ai",  # 非用户源
            "content": "AI回复",
            "task_id": "task_123"
        }
        
        await task_processor.process_memory_update(event_data)
        
        # 验证AI处理器未被调用
        assert task_processor.ai_processor.process_text.call_count == 0
        
        # 验证Redis未被调用
        assert mock_redis.publish.call_count == 0
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_process_memory_update_missing_content(self, task_processor, mock_redis):
        """测试记忆更新处理 - 缺少内容"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        # 创建模拟的AI处理器
        task_processor.ai_processor = AsyncMock()
        
        event_data = {
            "user_id": "test_user",
            "message_id": "msg_123",
            "source": "user",
            # 缺少content字段
            "task_id": "task_123"
        }
        
        await task_processor.process_memory_update(event_data)
        
        # 验证AI处理器未被调用
        assert task_processor.ai_processor.process_text.call_count == 0
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_publish_ai_response(self, task_processor, mock_redis):
        """测试发布AI响应"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        user_id = "test_user"
        response_text = "这是AI回复"
        original_message_id = "msg_123"
        
        await task_processor._publish_ai_response(user_id, response_text, original_message_id)
        
        # 验证Redis发布被调用
        mock_redis.publish.assert_called_once()
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_process_text_task(self, task_processor, mock_redis):
        """测试文本任务处理"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        # 创建模拟的AI处理器
        task_processor.ai_processor = AsyncMock()
        task_processor.ai_processor.process_text = AsyncMock(return_value="模拟的AI回复")
        
        task_id = "task_123"
        input_file = "test_input.txt"
        
        # 使用patch模拟文件读取
        with patch("builtins.open", mock_open(read_data="测试输入文本")):
            await task_processor._process_text_task(task_id, input_file)
        
        # 验证AI处理器被调用
        task_processor.ai_processor.process_text.assert_called_once_with("测试输入文本")
        
        # 验证Redis发布被调用
        mock_redis.publish.assert_called_once()
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_process_audio_task(self, task_processor, mock_redis):
        """测试音频任务处理"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        # 创建模拟的AI处理器
        task_processor.ai_processor = AsyncMock()
        task_processor.ai_processor.process_audio = AsyncMock(return_value=("模拟的AI回复", None))
        
        task_id = "task_123"
        input_file = "test_audio.wav"
        
        await task_processor._process_audio_task(task_id, input_file)
        
        # 验证AI处理器被调用
        task_processor.ai_processor.process_audio.assert_called_once_with(input_file)
        
        # 验证Redis发布被调用
        mock_redis.publish.assert_called_once()
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_send_response(self, task_processor, mock_redis):
        """测试发送响应"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        task_id = "task_123"
        text = "测试回复"
        audio_file = None
        
        await task_processor._send_response(task_id, text, audio_file)
        
        # 验证Redis发布被调用
        mock_redis.publish.assert_called_once()
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_send_error_response(self, task_processor, mock_redis):
        """测试发送错误响应"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        task_id = "task_123"
        error_message = "测试错误"
        
        await task_processor._send_error_response(task_id, error_message)
        
        # 验证Redis发布被调用
        mock_redis.publish.assert_called_once()
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_request_tts_synthesis(self, task_processor, mock_redis):
        """测试请求TTS合成"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        text = "测试文本"
        message_id = "msg_123"
        task_id = "task_123"
        
        await task_processor._request_tts_synthesis(text, message_id, task_id)
        
        # 验证Redis lpush被调用
        mock_redis.lpush.assert_called_once()
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_process_text_task_error(self, task_processor, mock_redis):
        """测试文本任务处理 - 错误情况"""
        # 设置模拟Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis
        
        task_id = "task_123"
        input_file = "nonexistent_file.txt"
        
        await task_processor._process_text_task(task_id, input_file)
        
        # 验证发送错误响应被调用
        mock_redis.publish.assert_called_once()
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client