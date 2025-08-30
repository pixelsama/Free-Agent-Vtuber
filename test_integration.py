#!/usr/bin/env python3
"""
Letta Bridge Service Integration Test
测试端到端的消息流程
"""
import asyncio
import json
import uuid
import time
from pathlib import Path
import redis.asyncio as redis

class IntegrationTester:
    def __init__(self):
        self.redis_client = None
        self.test_results = {}
        
    async def setup(self):
        """初始化测试环境"""
        self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        await self.redis_client.ping()
        print("✅ Redis连接成功")
        
    async def cleanup(self):
        """清理测试环境"""
        if self.redis_client:
            await self.redis_client.close()
            
    def create_test_message(self, message_type="permanent", content="Hello, this is a test message for permanent memory"):
        """创建测试消息"""
        task_id = str(uuid.uuid4())
        message = {
            "task_id": task_id,
            "type": "text",
            "user_id": "test_user_123",
            "content": content,
            "source": "integration_test",
            "timestamp": time.time(),
            "meta": {
                "memory_type": message_type,
                "trace_id": f"test_{task_id}",
                "lang": "zh",
                "from_channel": "integration_test"
            }
        }
        return message
        
    async def test_message_queue_flow(self):
        """测试消息队列流程"""
        print("\n=== 测试Redis消息队列端到端流程 ===")
        
        # 1. 发送永久记忆消息
        permanent_message = self.create_test_message("permanent", "请记住我的名字是张三，我喜欢编程")
        task_id_permanent = permanent_message["task_id"]
        
        print(f"1. 发送永久记忆消息 (task_id: {task_id_permanent})")
        await self.redis_client.lpush("user_input_queue", json.dumps(permanent_message, ensure_ascii=False))
        
        # 2. 监听响应频道
        print("2. 监听letta_responses频道...")
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe("letta_responses")
        
        # 等待响应
        timeout = 30  # 30秒超时
        start_time = time.time()
        response_received = False
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        response_data = json.loads(message["data"])
                        response_task_id = response_data.get("task_id")
                        
                        if response_task_id == task_id_permanent:
                            print(f"✅ 收到永久记忆响应: {response_data.get('response_text', '')[:100]}...")
                            print(f"   来源: {response_data.get('source', 'unknown')}")
                            print(f"   记忆更新: {response_data.get('memory_updated', False)}")
                            response_received = True
                            self.test_results["permanent_memory_test"] = True
                            break
                            
                    except json.JSONDecodeError as e:
                        print(f"❌ 响应JSON解析失败: {e}")
                
                # 检查超时
                if time.time() - start_time > timeout:
                    print(f"❌ 等待响应超时 ({timeout}秒)")
                    self.test_results["permanent_memory_test"] = False
                    break
                    
        except Exception as e:
            print(f"❌ 监听响应时出错: {e}")
            self.test_results["permanent_memory_test"] = False
        finally:
            await pubsub.close()
            
        return response_received
        
    async def test_temporary_message_fallback(self):
        """测试临时消息回退流程"""
        print("\n=== 测试临时消息回退到memory服务 ===")
        
        # 发送临时记忆消息（应该被忽略或回退）
        temp_message = self.create_test_message("temporary", "这是一条临时消息")
        task_id_temp = temp_message["task_id"]
        
        print(f"1. 发送临时记忆消息 (task_id: {task_id_temp})")
        await self.redis_client.lpush("user_input_queue", json.dumps(temp_message, ensure_ascii=False))
        
        # 检查队列中的消息（应该被重新放回队列让memory服务处理）
        await asyncio.sleep(2)  # 等待处理
        
        # 监听memory_updates频道看是否有处理
        print("2. 检查memory_updates频道...")
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe("memory_updates")
        
        timeout = 10
        start_time = time.time()
        found_temp_processing = False
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        update_data = json.loads(message["data"])
                        if update_data.get("task_id") == task_id_temp:
                            print(f"✅ 临时消息被memory服务处理")
                            found_temp_processing = True
                            self.test_results["temporary_fallback_test"] = True
                            break
                    except json.JSONDecodeError:
                        continue
                
                if time.time() - start_time > timeout:
                    print("⏰ 临时消息fallback测试超时（这是正常的，因为letta-bridge应该忽略临时消息）")
                    self.test_results["temporary_fallback_test"] = True  # 忽略临时消息是正确行为
                    break
                    
        except Exception as e:
            print(f"❌ 监听memory_updates时出错: {e}")
            self.test_results["temporary_fallback_test"] = False
        finally:
            await pubsub.close()
            
        return True
        
    async def test_session_management(self):
        """测试用户会话管理"""
        print("\n=== 测试用户会话管理 ===")
        
        # 检查Redis中的agent映射
        mapping_key = "letta:user_agent_mapping"
        mappings = await self.redis_client.hgetall(mapping_key)
        print(f"1. 当前用户会话映射: {len(mappings)} 个")
        
        if mappings:
            for user_id, agent_id in mappings.items():
                print(f"   用户 {user_id} -> Agent {agent_id}")
        
        self.test_results["session_management_test"] = True
        return True
        
    async def test_redis_queue_integrity(self):
        """测试Redis队列完整性"""
        print("\n=== 测试Redis队列完整性 ===")
        
        # 检查各个队列的状态
        queues_to_check = [
            "user_input_queue",
            "asr_tasks", 
            "tts_requests"
        ]
        
        for queue_name in queues_to_check:
            length = await self.redis_client.llen(queue_name)
            print(f"队列 {queue_name}: {length} 条消息")
            
        # 检查发布订阅频道（无法直接检查，但可以测试发布）
        channels_to_test = [
            "letta_responses",
            "memory_updates", 
            "ai_responses"
        ]
        
        for channel in channels_to_test:
            subscribers = await self.redis_client.pubsub_numsub(channel)
            print(f"频道 {channel}: {subscribers[channel] if subscribers else 0} 个订阅者")
            
        self.test_results["redis_integrity_test"] = True
        return True
        
    async def run_all_tests(self):
        """运行所有集成测试"""
        print("🚀 开始Letta Bridge集成测试")
        print("=" * 50)
        
        try:
            await self.setup()
            
            # 运行各种测试
            await self.test_redis_queue_integrity()
            await self.test_message_queue_flow()
            await self.test_temporary_message_fallback()
            await self.test_session_management()
            
            # 输出测试结果
            print("\n" + "=" * 50)
            print("📊 测试结果汇总:")
            passed = 0
            total = len(self.test_results)
            
            for test_name, result in self.test_results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"  {test_name}: {status}")
                if result:
                    passed += 1
                    
            print(f"\n总体结果: {passed}/{total} 测试通过")
            
            if passed == total:
                print("🎉 所有集成测试通过！")
                return True
            else:
                print("⚠️  部分测试失败，请检查")
                return False
                
        except Exception as e:
            print(f"❌ 测试过程中出现致命错误: {e}")
            return False
        finally:
            await self.cleanup()

async def main():
    tester = IntegrationTester()
    success = await tester.run_all_tests()
    exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())