# Letta永久记忆服务集成计划

## 概述

将开源的Letta永久记忆系统作为微服务集成到Free-Agent-Vtuber项目中，实现AI虚拟主播的长期记忆能力。

## 目标

- **永久记忆**：实现跨会话的记忆保持和学习能力
- **无缝集成**：保持现有架构不变，通过桥接模式集成
- **双重记忆**：短期记忆(memory-python) + 长期记忆(letta)并行运行
- **渐进升级**：可选择性启用，不影响现有功能

## 架构设计

### 微服务架构扩展

```
原有流程：
user_input_queue → memory-python → memory_updates → chat-ai

新增流程：
user_input_queue → letta-bridge-python → letta-api
                ↘ memory-python (保留)
```

### 新增服务

#### 1. letta容器
- **镜像**：`letta/letta:latest`
- **端口**：8283
- **数据存储**：PostgreSQL
- **职责**：提供永久记忆API服务

#### 2. letta-bridge-python
- **类型**：自开发Python微服务
- **职责**：Redis消息系统与Letta API之间的桥接
- **功能**：
  - 消息格式转换
  - 用户会话管理
  - 错误处理和重试

## 数据流设计

### Redis消息扩展

#### 新增队列
- `letta_requests` (list)：Letta专用任务队列
- `letta_responses` (pub/sub)：Letta处理结果发布

#### 消息格式

**输入消息**（继承现有格式）：
```json
{
  "task_id": "uuid",
  "type": "text|audio", 
  "user_id": "anonymous",
  "content": "用户输入内容",
  "timestamp": 1234567890,
  "meta": {
    "memory_type": "permanent|temporary",
    "trace_id": "...",
    "lang": "zh"
  }
}
```

**Letta API调用格式**：
```json
{
  "agent_id": "user_agent_mapping",
  "message": "用户输入内容",
  "stream": false
}
```

**输出消息**：
```json
{
  "task_id": "inherited",
  "user_id": "anonymous", 
  "response_text": "AI回复内容",
  "memory_updated": true,
  "source": "letta",
  "timestamp": 1234567890
}
```

## 目录结构

### 项目数据目录
```
Free-Agent-Vtuber/
├── data/                    # 新增：项目数据根目录
│   ├── letta/              # Letta服务数据
│   │   ├── pgdata/         # PostgreSQL数据
│   │   ├── config/         # 配置文件
│   │   └── logs/           # 日志文件
│   ├── memory/             # 现有memory服务数据
│   └── uploads/            # 用户上传文件
├── services/
│   ├── letta-bridge-python/  # 新增桥接服务
│   └── ...                   # 现有服务
```

### 服务结构
```
services/letta-bridge-python/
├── Dockerfile
├── requirements.txt
├── config.json
├── main.py              # 服务入口
├── letta_client.py      # Letta API客户端
├── message_processor.py # Redis消息处理
├── session_manager.py   # 用户会话管理
└── tests/
    ├── unit/
    └── integration/
```

## Docker配置

### docker-compose.yml扩展
```yaml
services:
  # 现有服务保持不变
  
  # 新增Letta服务
  letta:
    image: letta/letta:latest
    container_name: aivtuber-letta
    ports:
      - "8283:8283"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LETTA_MODEL=${LETTA_MODEL:-gpt-4}
    volumes:
      - ./data/letta/pgdata:/var/lib/postgresql/data
      - ./data/letta/config:/app/.letta
      - ./data/letta/logs:/app/logs
    restart: unless-stopped
    depends_on:
      - redis

  # 新增桥接服务
  letta-bridge:
    build: ./services/letta-bridge-python
    container_name: aivtuber-letta-bridge
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - LETTA_API_URL=http://letta:8283
      - LETTA_API_KEY=${LETTA_API_KEY}
    volumes:
      - ./services/letta-bridge-python:/app
      - ./utils:/app/shared_utils
    restart: unless-stopped
    depends_on:
      - redis
      - letta
```

### 开发环境支持
```yaml
# docker-compose.dev.yml中添加热重载
letta-bridge:
  # ...其他配置
  command: ["python", "dev_runner.py"]  # 热重载支持
  volumes:
    - ./services/letta-bridge-python:/app
```

## 实施计划

### 阶段1：基础集成（1-2天）
- [ ] 创建项目数据目录结构
- [ ] 配置Letta容器到docker-compose
- [ ] 验证Letta服务独立运行
- [ ] 测试Letta API基本调用

### 阶段2：桥接服务开发（2-3天）
- [ ] 创建letta-bridge-python服务结构
- [ ] 实现Redis消息监听
- [ ] 实现Letta API客户端
- [ ] 实现消息格式转换
- [ ] 添加用户会话管理

### 阶段3：集成测试（1天）
- [ ] 端到端消息流测试
- [ ] 错误处理和重试机制
- [ ] 性能和延迟测试
- [ ] 与现有服务兼容性验证

### 阶段4：生产就绪（1天）
- [ ] 添加监控和日志
- [ ] 配置健康检查
- [ ] 文档更新和部署指南
- [ ] 备份和恢复策略

## 配置管理

### 环境变量
```bash
# Letta配置
LETTA_API_KEY=your_letta_api_key
LETTA_MODEL=gpt-4
LETTA_MEMORY_BACKEND=postgresql

# Bridge服务配置
LETTA_API_URL=http://letta:8283
LETTA_TIMEOUT=30
LETTA_RETRY_ATTEMPTS=3
```

### 功能开关
```json
{
  "letta": {
    "enabled": true,
    "fallback_to_memory": true,
    "memory_type_routing": {
      "permanent": "letta",
      "temporary": "memory-python"
    }
  }
}
```

## 运维考虑

### 监控指标
- Letta API响应时间
- 消息处理成功率
- 用户会话数量
- 内存使用情况

### 备份策略
```bash
# 数据备份
docker-compose exec letta pg_dump letta > backup.sql

# 完整数据目录备份
tar -czf letta-backup-$(date +%Y%m%d).tar.gz data/letta/
```

### 故障恢复
- Letta服务异常时自动回退到memory-python
- PostgreSQL数据损坏时从备份恢复
- 网络分区时的消息队列重放

## 风险评估

### 技术风险
- **低**：Letta API稳定性
- **中**：消息格式兼容性
- **低**：容器网络通信

### 运维风险  
- **中**：数据备份和恢复
- **低**：服务监控和告警
- **中**：性能调优需求

### 缓解措施
- 保留现有memory服务作为备份
- 渐进式部署和测试
- 完整的回滚方案

## 成功标准

- [ ] Letta服务稳定运行，响应时间<2秒
- [ ] 现有功能完全不受影响
- [ ] 用户可以选择启用/禁用永久记忆
- [ ] 系统整体稳定性不下降
- [ ] 文档和部署流程完善

## 后续优化

### 性能优化
- Letta响应缓存
- 会话状态预加载
- 批量消息处理

### 功能扩展
- 多Agent支持
- 记忆内容分类
- 用户个性化配置

---

**文档版本**：v1.0  
**创建日期**：2025-08-29  
**负责人**：架构团队