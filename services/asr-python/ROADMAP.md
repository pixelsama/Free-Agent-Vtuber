# ASR 模块路线图与阶段规划

本文档记录当前 ASR 模块的实现进度与后续阶段规划，便于团队同步与执行。

## 一、当前进度（MVP 已完成）

1) 新增 ASR 微服务模块（services/asr-python）
- config.json：包含并发、Redis 队列/频道、Provider 配置（默认 fake，可切换 openai_whisper）
- requirements.txt：redis、httpx、pydantic、uvloop（非 Windows）
- main.py：
  - 异步消费 asr_tasks（Redis list，BLPOP）
  - 调用 Provider 完成转写
  - 通过 asr_results（Pub/Sub 频道）发布结果
  - 超时控制与错误处理
- providers/openai_whisper.py：
  - OpenAI Whisper 占位实现（需 OPENAI_API_KEY）
  - 以本地 WAV 文件调用 /audio/transcriptions
- README.md：运行与调用说明

2) 网关对接（方案 A）
- 新增 Flask Blueprint：services/gateway-python/asr_routes.py（POST /api/asr）
- 在 FastAPI 主应用挂载 WSGI：services/gateway-python/main.py（最终外部路由为 /api/asr）
- 行为：校验绝对路径 → 入队 asr_tasks → 返回 task_id

3) 测试（以模块目录为根运行）
- ASR 单测：services/asr-python/tests/unit/test_asr_service.py
  - build_provider("fake") → FakeProvider
  - 使用 DummyRedis 入队/出队，运行 worker_loop，断言发布 finished 且 text="测试文本"
- Gateway 单测：services/gateway-python/tests/unit/test_asr_route.py
  - 相对路径 400
  - monkeypatch get_redis 为 DummyRedis，断言 lpush 队列与消息结构

4) 自测方法（摘要）
- ASR：
  ```
  cd services/asr-python
  python -m venv venv && source venv/bin/activate
  pip install -r requirements.txt pytest pytest-asyncio
  pytest tests/unit -v
  python main.py
  ```
- Gateway：
  ```
  cd services/gateway-python
  python -m venv venv && source venv/bin/activate
  pip install -r requirements.txt -r requirements-test.txt
  pytest tests/unit -v
  python main.py
  ```
- 发送任务：
  ```
  curl -X POST http://localhost:8000/api/asr \
    -H "Content-Type: application/json" \
    -d '{"path":"/tmp/sample.wav","options":{"lang":"zh","timestamps":true}}'
  ```
- 订阅结果：
  ```
  redis-cli SUBSCRIBE asr_results
  ```

## 二、后续阶段规划（建议迭代顺序）

### Phase X：FunASR 本地 ASR 支持
- 目标：在本地环境引入 FunASR 中文通用模型的离线识别能力，作为可与 Fake/OpenAI Whisper 互换的 Provider 选项；首版仅输出整体文本 text，words 留空。
- 依赖：funasr、modelscope（直接加入 requirements.txt）；torch 由用户按设备（CPU/GPU）自行安装适配版本。
- 模型缓存：
  - 默认：~/.cache/modelscope（容器中通常为 /root/.cache/modelscope）
  - 可配置：provider.options.cache_dir（推荐生产部署指定到持久化目录，如 /data/models/modelscope）
- 配置示例（README 展示，不强制修改默认 config.json）：
  ```
  "provider": {
    "name": "funasr_local",
    "timeout_sec": 120,
    "max_retries": 1,
    "options": {
      "model_id": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
      "device": "cpu",
      "timestamps": false,
      "diarization": false,
      "cache_dir": "/data/models/modelscope"
    }
  }
  ```
- 交付物：
  - services/asr-python/providers/funasr_local.py（实现 BaseASRProvider，返回整体文本）
  - providers/factory.py 注册 "funasr_local"
  - requirements.txt 增加 funasr、modelscope
  - README 增加“使用 FunASR（本地）”章节（安装顺序、缓存与挂载、示例配置）
  - tests/unit/test_funasr_provider.py（monkeypatch FunASR 加载/推理为 Dummy，避免实际下载）
- 风险与注意：
  - 模型体积与首次下载耗时较长；建议通过 cache_dir 进行持久化与复用
  - torch 版本与 CUDA 兼容性差异；README 指引按官方方式安装
  - 时间戳/说话人分离后续迭代，首版仅 text
- 验收标准：
  - 配置切换为 funasr_local 后，能够消费任务并发布 finished 文本结果
  - 单元测试稳定，不依赖外网下载
  - 失败路径（文件不存在/模型加载失败）有清晰错误映射与日志

### Phase 2：Provider 扩展与配置健壮性
- 完成 OpenAI Whisper 真实实现：失败重试、超时、错误映射、日志脱敏
- Provider 工厂拆分文件结构（与 tts-python providers 对齐）：新增 asr_provider.py 抽象与 factory.py
- 引入 Pydantic 配置/消息模型，启动时严格校验 config 与入队消息
- 集成测试：对接真实 Redis，使用 FakeProvider 验证端到端（可衔接 docker-compose）

交付物：
- services/asr-python/providers/{asr_provider.py,factory.py}
- pydantic 模型与校验
- tests/integration/ 基础用例

### Phase 3：结果持久化与查询接口
- 结果除 Pub/Sub 发布外，写入 Redis Hash：asr_results:{task_id}
- Gateway 提供 GET /api/asr/{task_id} 查询接口，便于前端轮询
- 增加单测与集成测（查询接口）

交付物：
- gateway 新增查询路由与测试
- asr-python 写入 Hash 的实现及测试

### Phase 4：上传与转码（网关）
- 新增 POST /api/asr/upload，支持 multipart 上传
- 存储到安全目录，统一转码为 16k/mono/wav（ffmpeg 或 python-soundfile）
- 新增 audio 工具模块：重采样、格式识别、时长/大小限制
- 安全：白名单后缀、最大大小、最大时长

交付物：
- 网关上传/转码代码与单测
- asr-python/utils/audio.py 实作与测试

### Phase 5：Redis Streams 与消费组
- 任务从 list 迁移到 streams（XADD/XREADGROUP）
- 支持消费组与 offset 管理，提升稳定性与伸缩性
- 保留回退：通过配置在 list/streams 之间切换

交付物：
- asr-python 支持 streams 模式（可配置）
- 压测脚本与稳定性测试报告

### Phase 6：流式增量转写与分片合并
- 协议扩展：任务支持 streaming: true
- ASR 服务增量发布 partial 消息（status=partial, delta, is_final）
- Provider 接口增加异步迭代器（AsyncIterator），支持边识别边输出
- 分片合并策略与迟到片段处理

交付物：
- provider 接口扩展、服务发布逻辑
- 集成测试与模拟流式输入工具

### Phase 7：高级能力
- 说话人分离（对接第三方或本地 pyannote）
- 词级时间戳与置信度
- 热词/领域词典支持（视供应商能力）

交付物：
- 可选 provider 扩展与相关配置
- 对应单测与文档说明

### Phase 8：可观测性与运维
- 统一结构化日志、trace_id 透传
- 健康检查与指标（处理时延、队列堆积、失败率）
- manager 面板：ASR 任务监控、队列/频道可视化

交付物：
- metrics 采集（如 Prometheus）
- manager 页面与后端 API

## 三、优先级建议

1) 结果持久化 + 查询接口（Phase 3）
2) Provider 工厂拆分与 Pydantic 校验（Phase 2 的剩余部分）
3) 上传与转码（Phase 4）
4) Streams（Phase 5）
5) 流式增量转写（Phase 6）
6) 高级能力与可观测性（Phase 7/8）

## 四、决策点（需产品/团队确认）

- 查询接口输出格式与保留时长
- 上传目录与容量上限、清理策略
- 是否在 CI 中以 OPENAI_API_KEY 进行慢测（缺少 key 时自动跳过）

若需调整优先级或技术选型，请在评审会上确认后更新本路线图。
