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
│   ├── gateway-python/     # 网关模块
│   ├── input-handler-python/  # 输入处理模块
│   ├── memory-python/      # 记忆管理模块
│   └── output-handler-python/ # 输出处理模块
├── tests/                  # 测试目录
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

### 服务间通信
- 所有服务通过 Redis 进行通信
- 每个服务独立运行，拥有独立的虚拟环境
- 使用发布/订阅模式进行事件通知

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
- **运行所有测试**: `pytest tests/ -v`
- **运行单元测试**: `pytest tests/unit/ -v`
- **运行集成测试**: `pytest tests/integration/ -v`
- **测试覆盖率**: `pytest tests/ --cov=services --cov-report=html`
- **特定模块测试**: `pytest tests/unit/test_memory_manager.py -v`

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
- ✅ 记忆管理模块
- ✅ Web 管理界面
- ✅ 测试框架

进行中:
- 🚧 各模块功能完善
- 🚧 模块间通信优化
- 🚧 错误处理完善

待开发:
- ⏳ VTube Studio 集成
- ⏳ TTS 语音合成
- ⏳ 完整的对话流程

## 开发指南

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