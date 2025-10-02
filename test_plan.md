## 项目分析总结

从分析中可以看出，您的 AIVtuber 项目当前包含以下核心微服务：
1. **dialog-engine**：统一编排 ASR、LLM 对话、记忆和同步 TTS，提供 `/chat/*` 接口
2. **gateway-python**：API 网关，负责 WebSocket 连接路由
3. **input-handler-python**：输入处理服务，接收用户输入并直接调用 dialog-engine
4. **output-handler-python**：输出处理服务，订阅 `task_response:{task_id}` 并向前端推送结果
5. **memory-python**：记忆管理服务，负责存储和管理对话历史
6. **long-term-memory-python** 与 **async-workers**：提供长期记忆及分析扩展能力

所有服务都使用Redis进行通信，采用异步处理模式。

## 测试编写计划

我建议按以下顺序为各个模块编写测试：

### 1. 测试框架和环境
- 使用pytest作为主要测试框架（已在requirements-dev.txt中配置）
- 使用pytest-asyncio支持异步测试
- 使用pytest-mock进行模拟测试

### 2. 各模块测试策略

#### dialog-engine 测试重点：
- `/chat/stream` SSE 文本流的增量响应与完成事件
- `/chat/audio` 语音输入处理（包含 ASR provider mock/whisper）
- 短期记忆与长期记忆检索的集成
- TTS 推流（Mock/Edge）停止与异常回退
- 统计数据与 outbox 事件的正确性

#### gateway-python 测试重点：
- WebSocket连接代理功能
- CORS配置测试
- 健康检查端点
- 连接管理和清理

#### input-handler-python 测试重点：
- WebSocket 输入处理与任务组装
- 数据分块和重组
- 与 dialog-engine 的文本/音频接口交互
- Redis `task_response:{task_id}` 发布逻辑
- 临时文件管理

#### memory-python 测试重点：
- 消息存储和检索
- 记忆管理器功能
- Redis订阅/发布机制
- 定期清理功能

#### output-handler-python 测试重点：
- WebSocket 输出连接与状态跟踪
- Redis 响应监听与错误处理
- 音频分片推送（dialog-engine 推流）
- 超时与断线重试机制

### 3. 测试类型分类
- **单元测试**: 针对各个类和函数的独立功能测试
- **集成测试**: 测试服务间的交互和Redis通信
- **端到端测试**: 模拟完整的用户请求到响应流程

### 4. 实施建议
1. 先编写核心功能的单元测试
2. 然后编写集成测试验证服务间通信
3. 最后编写端到端测试验证完整流程
4. 使用mock对象模拟外部依赖（如Redis、AI API）
5. 确保测试覆盖率，特别是错误处理路径
