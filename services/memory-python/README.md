# Memory Service

AI虚拟主播记忆模块，负责存储和管理对话历史，支持事件驱动的AI响应机制。

## 功能特性

- **短期记忆管理**: 存储用户对话历史和AI回复
- **事件驱动架构**: 通过Redis Pub/Sub触发AI处理
- **智能过滤**: 区分用户输入和AI回复，避免无限循环
- **上下文管理**: 提供可配置的对话上下文窗口
- **自动清理**: 定期清理过期记忆数据

## 核心组件

### MemoryManager
- 记忆存储和检索
- Redis Pub/Sub事件发布
- 上下文管理
- 自动清理

### MemoryService
- 处理用户输入存储
- 处理AI回复存储
- 任务管理

### 事件监听器
- 输入队列监听
- AI响应监听
- 定期清理调度

## 配置说明

- `max_memory_size`: 单用户最大记忆条数
- `memory_ttl_hours`: 记忆过期时间(小时)
- `context_window`: 上下文窗口大小
- `enable_global_context`: 是否启用全局上下文
- `cleanup_interval_hours`: 清理间隔(小时)

## 运行

```bash
cd services/memory-python
pip install -r requirements.txt
python main.py
```