import json
from unittest.mock import AsyncMock, Mock

import pytest

from main import AIProcessor


class TestAIProcessor:
    """AI处理器单元测试"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("你好", ["你好", "很高兴"]),
            ("今天天气怎么样", ["天气"]),
            ("谢谢你", ["不用谢", "很开心"]),
            ("什么是AI？", ["问题", "话题"]),
            ("我想杀人", ["不开心", "别"]),
            ("这是一个测试消息", ["有意思", "测试"]),
        ],
    )
    async def test_process_with_rules(self, ai_processor, text, expected):
        """测试规则处理"""
        response = ai_processor._process_with_rules(text)
        assert any(sub in response for sub in expected)

    @pytest.mark.asyncio
    async def test_process_text_with_fallback_rules(self, ai_processor):
        """测试文本处理 - 回退到规则"""
        # 模拟没有AI客户端的情况
        import main as main_module

        original_ai_client = main_module.ai_client
        main_module.ai_client = None

        text = "你好"
        response = await ai_processor.process_text(text)
        assert "你好" in response or "很高兴" in response

        # 恢复原始AI客户端
        main_module.ai_client = original_ai_client

    @pytest.mark.asyncio
    async def test_process_text_no_ai_no_fallback(self, ai_processor):
        """测试文本处理 - 没有AI且不回退"""
        # 模拟没有AI客户端且不回退的情况
        import main as main_module

        original_ai_client = main_module.ai_client
        original_fallback = ai_processor.fallback_to_rules

        main_module.ai_client = None
        ai_processor.fallback_to_rules = False

        text = "你好"
        response = await ai_processor.process_text(text)
        assert "不可用" in response or "请稍后" in response

        # 恢复原始设置
        main_module.ai_client = original_ai_client
        ai_processor.fallback_to_rules = original_fallback

    @pytest.mark.asyncio
    async def test_process_with_ai_success(self, ai_processor, mock_ai_client):
        """测试AI处理 - 成功情况"""
        # 设置模拟AI客户端
        import main as main_module

        original_ai_client = main_module.ai_client
        main_module.ai_client = mock_ai_client

        text = "这是一个测试问题"
        response = await ai_processor._process_with_ai(text)
        assert "模拟的AI回复" in response

        # 验证AI客户端被调用
        mock_ai_client.chat.completions.create.assert_called_once()

        # 恢复原始AI客户端
        main_module.ai_client = original_ai_client

    @pytest.mark.asyncio
    async def test_process_with_ai_error_fallback(self, ai_processor, mock_ai_client):
        """测试AI处理 - 错误回退到规则"""
        # 设置模拟AI客户端抛出异常
        import main as main_module

        original_ai_client = main_module.ai_client
        mock_ai_client.chat.completions.create.side_effect = Exception("API错误")
        main_module.ai_client = mock_ai_client

        text = "这是一个测试问题"
        response = await ai_processor.process_text(text)

        # 应该回退到规则回复
        assert "有意思" in response or "测试" in response

        # 恢复原始AI客户端
        main_module.ai_client = original_ai_client

    @pytest.mark.asyncio
    async def test_get_global_context_success(self, ai_processor, mock_redis):
        """测试获取全局上下文 - 成功情况"""
        # 设置模拟Redis客户端
        import main as main_module

        original_redis_client = main_module.redis_client
        main_module.redis_client = mock_redis

        # 模拟Redis返回的数据
        mock_messages = [
            json.dumps({"user_id": "test_user", "content": "你好", "source": "user"}),
            json.dumps(
                {"user_id": "test_user", "content": "你好！我是AI助手", "source": "ai"}
            ),
        ]
        mock_redis.lrange.return_value = mock_messages

        context = await ai_processor._get_global_context()
        assert len(context) == 2
        assert context[0]["content"] == "你好"
        assert context[1]["content"] == "你好！我是AI助手"

        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client

    @pytest.mark.asyncio
    async def test_get_global_context_error(self, ai_processor, mock_redis):
        """测试获取全局上下文 - 错误情况"""
        # 设置模拟Redis客户端抛出异常
        import main as main_module

        original_redis_client = main_module.redis_client
        mock_redis.lrange.side_effect = Exception("Redis错误")
        main_module.redis_client = mock_redis

        context = await ai_processor._get_global_context()
        assert context == []  # 应该返回空列表

        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client

    @pytest.mark.asyncio
    async def test_process_audio(self, ai_processor):
        """测试音频处理"""
        audio_file = "test_audio.wav"
        response_text, response_audio = await ai_processor.process_audio(audio_file)

        # 验证返回了文本回复
        assert isinstance(response_text, str)
        assert len(response_text) > 0

        # 验证音频文件为None（当前是模拟实现）
        assert response_audio is None
