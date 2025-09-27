# MCP 工具集成计划文档

## 项目概述

本文档详细说明了在 Free-Agent-Vtuber 项目中集成 Model Context Protocol (MCP) 工具的完整计划。MCP 是一种标准化协议，用于在 AI 应用程序中集成外部工具和数据源。

## 目标与愿景

### 核心目标
- **无缝集成**：将 MCP 工具无缝集成到现有的对话引擎中
- **保持流畅性**：确保工具调用不影响现有的 SSE 流式对话体验
- **模块化设计**：通过独立模块管理 MCP 工具，便于维护和扩展
- **可靠性保证**：实现可靠的消息传递和错误处理机制

### 技术愿景
- 支持多种 MCP 工具类型（搜索、计算、API 调用等）
- 提供实时的工具执行状态反馈
- 建立完善的监控和日志系统
- 支持工具链式调用和复杂工作流

## 技术架构

### 整体架构图
```
┌─────────────────────┐
│   Frontend (SSE)    │
│                     │
└──────────┬──────────┘
           │ SSE Stream
           ▼
┌─────────────────────┐
│   Dialog Engine     │
│   (ChatService)     │
└──────────┬──────────┘
           │ Tool Call Event
           ▼
┌─────────────────────┐       ┌─────────────────────┐
│  Redis Streams      │◄─────►│   MCP Tool Worker   │
│  (events.plugins)   │       │   (plugins-mcp)     │
└─────────────────────┘       └─────────┬───────────┘
                                        │
                                        ▼
                               ┌─────────────────────┐
                               │   External MCP      │
                               │   Tools/Services    │
                               └─────────────────────┘
```

### 组件说明
1. **Dialog Engine**: 现有的对话引擎，负责检测和协调工具调用
2. **Redis Streams**: 消息队列，处理工具请求的异步分发
3. **MCP Tool Worker**: 新建模块，专门处理 MCP 工具调用
4. **External MCP Tools**: 外部 MCP 兼容的工具和服务

## 实施计划

### Phase 1: 基础架构准备 (第1-2周)

#### 1.1 LLM 客户端扩展
- **目标**: 扩展 `OpenAIChatClient` 支持工具调用检测
- **任务**:
  - 修改 `stream_chat` 方法，捕获 `tool_calls` 事件
  - 实现工具调用控制事件机制
  - 添加相应的单元测试

#### 1.2 对话服务改造
- **目标**: 更新 `ChatService` 支持工具调用工作流
- **任务**:
  - 在流式响应中集成工具调用检测
  - 实现 SSE 控制消息（工具执行状态）
  - 添加工具结果回传处理逻辑

### Phase 2: 消息队列集成 (第3-4周)

#### 2.1 Redis Streams 配置
- **目标**: 配置 `events.plugins` 流处理工具请求
- **任务**:
  - 扩展 Outbox 模式支持插件事件
  - 设计工具调用事件数据结构
  - 实现事件路由配置

#### 2.2 事件数据结构设计
```json
{
  "eventType": "PluginToolCallRequested",
  "correlationId": "unique-request-id",
  "sessionId": "user-session-id",
  "turn": 42,
  "toolCallId": "call_abc123",
  "toolName": "web_search",
  "arguments": {
    "query": "search terms",
    "max_results": 10
  },
  "responseChannel": "rpc.plugins.responses:unique-request-id",
  "timeout": 30000,
  "retryCount": 0
}
```

### Phase 3: MCP 工具模块开发 (第5-7周)

#### 3.1 模块结构
```
services/plugins-mcp/
├── main.py              # 主入口和消费者逻辑
├── mcp_client.py        # MCP 协议客户端
├── tool_registry.py     # 工具注册和管理
├── config.py           # 配置管理
├── monitoring.py       # 监控和指标
├── exceptions.py       # 异常定义
├── requirements.txt    # 依赖管理
├── Dockerfile         # 容器化配置
└── README.md          # 模块文档
```

#### 3.2 核心功能实现
- **MCP 客户端**: 实现 MCP 协议通信
- **工具注册**: 动态发现和注册可用工具
- **请求处理**: 处理来自 Redis Streams 的工具请求
- **结果回传**: 将工具执行结果发送回对话引擎

### Phase 4: 工具集成与测试 (第8-9周)

#### 4.1 支持的 MCP 工具类型
- **搜索工具**: 网络搜索、文档搜索
- **计算工具**: 数学计算、数据分析
- **API 工具**: 外部 API 调用、数据获取
- **文件工具**: 文件操作、内容处理

#### 4.2 测试策略
- **单元测试**: 各模块独立功能测试
- **集成测试**: 端到端工具调用流程测试
- **性能测试**: 并发工具调用性能测试
- **故障测试**: 异常情况和错误恢复测试

### Phase 5: 监控与运维 (第10周)

#### 5.1 监控指标
- 工具调用成功率
- 平均响应时间
- 队列积压情况
- 错误率统计

#### 5.2 日志系统
- 结构化日志记录
- 请求跟踪（correlationId）
- 性能指标记录
- 错误详情记录

## 配置管理

### 环境变量
```bash
# MCP 功能开关
ENABLE_MCP=true

# MCP 服务配置
MCP_SERVER_ENDPOINT=http://localhost:8080
MCP_API_KEY=your_api_key_here
MCP_REQUEST_TIMEOUT_MS=30000
MCP_MAX_RETRIES=3

# Redis 配置
REDIS_STREAMS_CONFIG=events.plugins

# 监控配置
MCP_METRICS_ENABLED=true
MCP_LOG_LEVEL=INFO
```

### 工具配置
```yaml
# tools_config.yaml
tools:
  web_search:
    enabled: true
    timeout: 10000
    max_results: 10

  calculator:
    enabled: true
    timeout: 5000
    precision: 10

  file_operations:
    enabled: false
    allowed_paths: ["/data", "/tmp"]
```

## 安全考虑

### 访问控制
- 工具权限管理
- API 密钥安全存储
- 用户会话验证

### 数据保护
- 敏感信息过滤
- 请求参数验证
- 结果内容审查

### 服务安全
- 网络隔离配置
- 超时和限流保护
- 异常处理和恢复

## 性能优化

### 缓存策略
- 工具结果缓存
- 频繁请求优化
- 会话状态缓存

### 并发处理
- 异步工具调用
- 连接池管理
- 资源限制控制

### 扩展性设计
- 水平扩展支持
- 负载均衡配置
- 服务发现机制

## 故障处理

### 错误分类
1. **网络错误**: 连接超时、网络中断
2. **工具错误**: 工具执行失败、参数错误
3. **系统错误**: 资源不足、服务不可用

### 恢复策略
- 自动重试机制
- 优雅降级处理
- 用户友好的错误提示

### 监控告警
- 实时错误监控
- 性能指标告警
- 服务健康检查

## 部署方案

### Docker 容器化
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "main.py"]
```

### Docker Compose 集成
```yaml
version: '3.8'
services:
  plugins-mcp:
    build: ./services/plugins-mcp
    environment:
      - ENABLE_MCP=true
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    networks:
      - vtuber-network
```

## 开发工具

### 调试工具
- MCP 协议调试器
- 工具调用模拟器
- 性能分析工具

### 开发环境
- 本地 MCP 服务器
- 测试数据生成器
- 自动化测试套件

## 文档和培训

### 技术文档
- API 参考文档
- 集成指南
- 故障排查手册

### 用户指南
- 工具使用说明
- 配置指南
- 最佳实践

## 时间线和里程碑

| 阶段 | 时间 | 关键交付物 | 成功标准 |
|------|------|------------|----------|
| Phase 1 | 第1-2周 | 基础架构扩展 | 工具调用检测功能完成 |
| Phase 2 | 第3-4周 | 消息队列集成 | 事件流处理正常运行 |
| Phase 3 | 第5-7周 | MCP 模块开发 | 核心功能模块完成 |
| Phase 4 | 第8-9周 | 工具集成测试 | 端到端测试通过 |
| Phase 5 | 第10周 | 监控运维准备 | 生产环境就绪 |

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| MCP 协议兼容性问题 | 中 | 高 | 提前进行 PoC 验证 |
| 性能瓶颈 | 中 | 中 | 早期性能测试和优化 |
| 安全漏洞 | 低 | 高 | 安全审查和渗透测试 |
| 集成复杂性 | 高 | 中 | 分阶段实施，降低复杂度 |

## 成功指标

### 技术指标
- 工具调用响应时间 < 5秒
- 系统可用性 > 99.9%
- 错误率 < 1%

### 业务指标
- 用户体验改善
- 功能覆盖度提升
- 维护成本控制

## 后续发展

### 短期目标 (3个月)
- 稳定的 MCP 工具集成
- 基础监控和运维能力
- 用户反馈收集和优化

### 中期目标 (6个月)
- 扩展更多工具类型
- 智能工具推荐
- 性能优化和扩展

### 长期目标 (1年)
- 完整的工具生态系统
- 自定义工具开发平台
- AI 驱动的工具编排

---

本计划文档将作为 MCP 工具集成项目的指导性文件，随着项目进展将持续更新和完善。