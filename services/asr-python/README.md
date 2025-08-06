# ASR Service (MVP)

可扩展的语音识别服务，当前支持：
- 任务来源：Redis list（BLPOP）队列
- 结果发布：Redis Pub/Sub 频道
- Provider：Fake（默认，用于联调）、OpenAI Whisper（占位，需设置 OPENAI_API_KEY）
- 输入：仅支持本地绝对路径的统一规格 WAV（16k/mono）

## 运行

1) 确保 Redis 已启动
```bash
redis-server
# 或使用项目 docker-compose.dev.yml
```

2) 安装依赖并启动
```bash
cd services/asr-python
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

可选：使用 OpenAI Whisper
```bash
export OPENAI_API_KEY=sk-xxx
# 修改 config.json 中 provider.name 为 "openai_whisper"（默认是 "fake"）
```

## 测试

本模块的测试以“模块目录”为根目录运行，请在 services/asr-python 下执行：

1) 安装测试依赖
```bash
cd services/asr-python
source venv/bin/activate  # 若尚未创建虚拟环境，请参考上文“运行”步骤
pip install pytest pytest-asyncio
```

2) 运行单元测试
```bash
pytest tests/unit -v
```

3) 测试说明
- tests/unit/test_asr_service.py
  - test_build_provider_fake：验证 build_provider("fake") 返回 FakeProvider
  - test_worker_loop_with_fake_provider：使用 DummyRedis 模拟队列/发布，运行 worker_loop，断言最终发布 finished 且 text="测试文本"
- 测试不依赖真实 Redis 与外部服务，执行快速稳定
- 后续如新增集成测试，请放在 tests/integration/ 并通过环境变量控制是否运行慢测（如 OPENAI_API_KEY 存在时启用 Whisper 调用）

## 配置

config.json
```json
{
  "service": {
    "name": "asr-python",
    "concurrency": 2,
    "log_level": "INFO"
  },
  "redis": {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "tasks_queue": "asr_tasks",
    "results_channel": "asr_results"
  },
  "provider": {
    "name": "fake",
    "timeout_sec": 60,
    "max_retries": 1,
    "options": {
      "lang": "zh",
      "timestamps": true,
      "diarization": false
    },
    "credentials": {
      "api_key_env": "OPENAI_API_KEY",
      "base_url": "https://api.openai.com/v1"
    }
  },
  "audio": {
    "target_sample_rate": 16000,
    "channels": 1,
    "max_duration_sec": 300
  }
}
```

## 网关对接

已在 gateway-python 挂载了 Flask Blueprint 到 FastAPI（WSGI）：
- 路由：POST /api/asr
- 请求：
```json
{
  "path": "/abs/path/to/file.wav",
  "options": { "lang": "zh", "timestamps": true }
}
```
- 响应：
```json
{ "task_id": "uuid" }
```

示例调用
```bash
curl -X POST http://localhost:8000/api/asr \
  -H "Content-Type: application/json" \
  -d '{"path":"/tmp/sample.wav","options":{"lang":"zh","timestamps":true}}'
```

ASR 服务将消费 Redis 队列 asr_tasks，并在完成后向频道 asr_results 发布消息：
```json
{
  "task_id": "...",
  "status": "finished",
  "text": "测试文本",
  "words": [],
  "provider": "fake",
  "lang": "zh",
  "error": null,
  "meta": { "source": "gateway" }
}
```

## 开发

- Provider 扩展：在 services/asr-python/providers/ 下新增文件，实现 `transcribe_file`，并在 `build_provider` 中注册。
- 未来计划：
  - 支持文件上传/转码（网关）
  - 支持 Redis streams（消费组）
  - 流式增量结果
  - 说话人分离与词级时间戳
