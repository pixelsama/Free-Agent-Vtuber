# Claude 开发助手配置

## 项目概述
- **项目名称**: AIVtuber - AI 虚拟主播系统
- **项目类型**: 基于事件驱动架构的 AI 虚拟主播
- **架构模式**: 微服务 + 事件驱动 (Redis 消息总线)
- **主要语言**: Python 3.10+
- **核心特点**: 高度解耦、技术异构、可扩展

## 技术栈
- **消息总线**: Redis
- **AI 模型**: Gemini 2.5 Flash (通过 OpenAI 兼容 API)
- **虚拟形象**: VTube Studio API
- **Web 管理**: Flask
- **测试框架**: pytest + pytest-asyncio
- **异步编程**: asyncio

## 项目结构
```
AIVtuber/
├── manager/                 # Flask 管理界面
├── services/               # 微服务模块
│   ├── chat-ai-python/     # AI 聊天模块
│   │   ├── tests/          # 单元测试目录
│   │   │   ├── unit/       # 单元测试
│   │   │   └── integration/ # 集成测试
│   │   └── (其他文件)
│   ├── gateway-python/     # 网关模块
│   │   ├── tests/          # 单元测试目录
│   │   │   ├── unit/       # 单元测试
│   │   │   └── integration/ # 集成测试
│   │   └── (其他文件)
│   ├── input-handler-python/  # 输入处理模块
│   │   ├── tests/          # 单元测试目录
│   │   │   ├── unit/       # 单元测试
│   │   │   └── integration/ # 集成测试
│   │   └── (其他文件)
│   ├── memory-python/      # 记忆管理模块
│   │   ├── tests/          # 单元测试目录
│   │   │   ├── unit/       # 单元测试
│   │   │   └── integration/ # 集成测试
│   │   └── (其他文件)
│   └── output-handler-python/ # 输出处理模块
│       ├── tests/          # 单元测试目录
│       │   ├── unit/       # 单元测试
│       │   └── integration/ # 集成测试
│       └── (其他文件)
├── docs/                   # 项目文档
└── dev-venv/              # 开发环境
```

## 开发约定

### 代码风格
- **Python**: 严格遵循 PEP 8 标准
- **异步编程**: 优先使用 asyncio，所有 I/O 操作异步化
- **配置管理**: 使用 JSON 格式配置文件 (config.json)
- **日志记录**: 使用 Python logging 模块，统一日志格式
- **错误处理**: 完善的异常处理和日志记录
- **类型注解**: 使用 typing 模块进行类型标注

### Redis 消息约定
- **队列命名**: 使用描述性名称，如 `user_input_queue`
- **消息格式**: JSON 格式，包含必要的元数据
- **频道命名**: 使用前缀区分用途，如 `memory_updates`

统一契约（新增/更新）：
- asr_tasks（list）：网关 → ASR（TaskMessage，见 asr-python/schemas.py）
- asr_results（pub/sub）：ASR → 全局（ResultMessage；status=finished 必须包含 text；failed 必须包含 error）
- user_input_queue（list）：input-handler → memory（content 优先）
  - 统一任务结构（示例）：
    {
      "task_id": "沿用上游，如 ASR task_id",
      "type": "text" | "audio",
      "user_id": "anonymous",
      "content": "识别文本（推荐）",
      "input_file": "/path/to/file（可选兜底）",
      "source": "asr" | "user" | "system",
      "timestamp": 1234567890,
      "meta": { "trace_id": "...", "lang": "zh", "from_channel": "asr_results", "provider": "fake|openai_whisper|funasr_local" }
    }
- memory_updates（pub/sub）：memory → chat-ai
- ai_responses（pub/sub）：chat-ai → memory 存档
- tts_requests（list）：chat-ai → tts
- task_response:{task_id}（pub/sub）：tts → output/gateway

### 服务间通信
- 所有服务通过 Redis 进行通信
- 每个服务独立运行，拥有独立的虚拟环境
- 使用发布/订阅模式进行事件通知
- 自 2025-08 起：输入归一化由 input-handler 承担。input-handler 订阅 ASR 的 asr_results，将 status=finished 的识别文本转为统一“用户输入任务”（content 优先）并入队 user_input_queue；memory 优先使用 content 字段，若无则回退读取 input_file。

## 开发环境

### 双环境架构
- **生产环境**: 各服务独立虚拟环境 (`services/*/venv/`)
- **开发环境**: 统一开发测试环境 (`dev-venv/`)

### 环境设置
```bash
# 激活开发环境
source dev-venv/bin/activate

# 安装开发依赖
pip install -r requirements-dev.txt
```

## 常用命令

### 测试命令
- **运行所有测试**: `cd services/<service-name> && pytest tests/ -v`
- **运行单元测试**: `cd services/<service-name> && pytest tests/unit/ -v`
- **运行集成测试**: `cd services/<service-name> && pytest tests/integration/ -v`
- **测试覆盖率**: `cd services/<service-name> && pytest tests/ --cov=. --cov-report=html`
- **特定模块测试**: `cd services/<service-name> && pytest tests/unit/test_<module>.py -v`

### 批量测试命令
- **运行所有服务的测试**: `for /d %i in (services/*) do cd %i && pytest tests/ -v && cd ../../`
- **运行所有单元测试**: `for /d %i in (services/*) do cd %i && pytest tests/unit/ -v && cd ../../`

### 构建和运行
- **启动管理器**: `cd manager && python app.py`
- **启动Redis**: `redis-server` (确保运行)
- **检查Redis**: `redis-cli ping` (应返回 PONG)

### 服务管理
- **启动单个服务**: 进入服务目录，激活 venv，运行 `python main.py`
- **通过管理器**: 访问 http://localhost:5000 使用 Web 界面

## AI 配置
- **Provider**: OpenAI 兼容 API
- **Model**: gemini-2.5-flash
- **API Base**: https://generativelanguage.googleapis.com/v1beta/openai/
- **Character**: 友好的AI虚拟主播"小艾"

## 开发阶段
当前处于: **Phase 1 - 架构骨架验证**

已完成:
- ✅ 项目架构设计
- ✅ 基础微服务框架
- ✅ Redis 消息总线
- ✅ 记忆管理模块（B 模式：content 优先，fallback 到 input_file）
- ✅ Web 管理界面
- ✅ 测试框架
- ✅ ASR → Input 归一化桥接（input-handler 订阅 asr_results → user_input_queue）

进行中:
- 🚧 各模块功能完善
- 🚧 模块间通信优化（结果持久化 + 查询接口、上传与统一转码）
- 🚧 错误处理完善

待开发:
- ⏳ VTube Studio 集成
- ⏳ TTS 语音合成
- ⏳ 完整的对话流程

## 开发指南

### 测试规范（统一标准）

以下规范来自最近在 services/asr-python 模块中实践并验证通过的经验总结，作为全仓库的统一标准，适用于所有 Python 服务模块（chat-ai-python、gateway-python、input-handler-python、memory-python、output-handler-python、tts-python 等）。

1) 目录与根路径
- 每个服务模块的测试均在该模块目录下运行，例如：
  - cd services/<service-name> && pytest tests/ -v
- 测试与运行都以“模块目录”为根目录，不依赖仓库根目录。

2) 可导入包与 PythonPath
- 模块目录必须是一个可导入包：在模块根目录创建 __init__.py。
- 在模块根目录添加 pytest.ini，显式指定当前目录进入 PythonPath，避免不同环境下 sys.path 差异导致的导入错误：
  [pytest]
  pythonpath = .
  asyncio_mode = strict

3) 模块化拆分与导入方式
- 不建议从入口脚本 main.py 直接导入被测逻辑。应将可复用逻辑拆分到独立模块（如 asr_service.py、providers/factory.py），测试从这些模块导入：
  from asr_service import RedisClient, worker_loop
  from providers.factory import build_provider
- 入口脚本仅负责装配（加载配置、创建依赖、启动服务），不承载业务实现。

4) Pydantic v2 数据模型与序列化
- 使用 Pydantic v2（BaseModel.model_dump/model_dump_json），禁止传入 ensure_ascii 等不兼容参数，统一：
  result_json = model.model_dump_json()
- 使用 Pydantic 对配置（AppConfig）与消息（TaskMessage、ResultMessage）进行强校验，尽早暴露错误。

5) 异步测试规范（pytest-asyncio）
- 统一使用 pytest-asyncio，asyncio_mode 设为 strict（见 pytest.ini）。
- 异步测试函数使用 @pytest.mark.asyncio 装饰。
- 若需要替代外部依赖（如 Redis），在测试中使用内存桩（Dummy 类）模拟网络调用，避免不必要的集成依赖，提升单测稳定性与速度。

6) Redis 交互测试策略
- 单元测试：使用 DummyRedis 内存桩对象替代真实 Redis，验证核心逻辑（如 BLPOP → Provider → 发布结果）。
- 集成测试（可选）：在 tests/integration/ 下编写，依赖 docker-compose.dev.yml 的 Redis，逐步增加端到端覆盖。

7) 消息契约与发布
- 入队消息（任务）：遵循统一 schema（示例：TaskMessage），最少字段包含 task_id、audio（type=file、path、format、sample_rate、channels）、options、meta。
- 出队消息（结果）：遵循 ResultMessage，status ∈ {finished, failed, partial}，finished 必须包含 text，failed 必须包含 error。
- 发布到 Redis 时，使用 Pydantic 的 model_dump_json() 输出 JSON 字符串，配合 Redis decode_responses=True。

8) 失败与超时处理
- 对外部调用（如 Provider）使用 asyncio.timeout 包裹，超时捕获为 asyncio.TimeoutError 并发布 failed。
- 统一错误日志与错误消息，便于排查与监控。

9) 测试命名与布局
- tests/unit/ 放置单元测试，tests/integration/ 放置集成测试。
- 测试文件命名：test_<module>.py；用例命名：test_<behavior>。
- 每个服务在 README 中包含“测试”章节，明确命令与注意事项。

10) 示例：内存桩（DummyRedis）单测模型
- 通过内存列表模拟队列与发布，避免真实 Redis：
  class DummyRedis(RedisClient):
      async def blpop(...): ...
      async def publish(...): ...
      async def lpush(...): ...
- 构造最小任务消息，运行 worker_loop，断言发布结果的字段与状态。

11) 约束与一致性
- 严禁在测试中依赖隐式 sys.path 行为（不同环境、插件可能不同），务必使用 __init__.py + pytest.ini 组合保障导入稳定。
- 入口脚本与可复用逻辑分离，保证测试无需导入 main.py。

落实示例（ASR 模块摘录）
- 包结构：
  services/asr-python/
  ├── __init__.py
  ├── pytest.ini                 # pythonpath = .
  ├── main.py                    # 入口：加载配置，调用 run_service
  ├── asr_service.py             # 核心逻辑：load_config、RedisClient、worker_loop、run_service
  ├── schemas.py                 # Pydantic：AppConfig/TaskMessage/ResultMessage
  ├── providers/
  │   ├── asr_provider.py        # BaseASRProvider、ASRResult
  │   └── factory.py             # FakeProvider、build_provider（支持 openai_whisper）
  └── tests/
      └── unit/
          └── test_asr_service.py

- 单测片段（简化）：
  from asr_service import RedisClient, worker_loop
  from providers.factory import FakeProvider, build_provider

  @pytest.mark.asyncio
  async def test_worker_loop_with_fake_provider():
      published, tasks = [], []
      class DummyRedis(RedisClient):
          ...
      # 入队任务 → 跑 loop → 断言结果 status=finished、text="测试文本"

以上规范已在 ASR 模块实践并通过，后续新增/改动模块应复用相同策略，确保一致性与可维护性。

### 添加新功能时
1. 首先理解现有代码结构和风格
2. 查看相关的配置文件和依赖
3. 编写相应的单元测试
4. 确保异步操作正确实现
5. 添加适当的日志和错误处理

### 修改现有模块时
1. 先运行现有测试确保基础功能正常
2. 保持向后兼容性
3. 更新相关测试用例
4. 检查对其他模块的影响

### 调试和问题排查
1. 检查 Redis 连接状态
2. 查看服务日志输出
3. 使用管理界面监控服务状态
4. 运行相关测试用例

## 注意事项
- 所有服务都应该能够独立启动和关闭
- Redis 是系统的核心依赖，确保其始终运行
- 配置文件中的敏感信息应该通过环境变量管理
- 新增依赖时需要同时更新对应的 requirements.txt
- 遵循微服务原则，避免模块间直接依赖
