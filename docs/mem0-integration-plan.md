# Mem0长期记忆模块集成方案

## 概述

本文档详细说明如何在Free-Agent-Vtuber项目中集成Mem0框架，实现长期记忆功能，增强虚拟主播的个性化交互体验。

## 1. 项目现状分析

### 1.1 现有架构
项目采用**微服务事件驱动架构**，使用Redis作为中央消息总线：

```
外部输入 → Gateway → ASR → input-handler → user_input_queue
         ↓
memory消费user_input_queue → memory_updates → chat-ai → ai_responses + tts_requests
         ↓
TTS消费tts_requests → task_response channels → output/gateway
```

### 1.2 现有记忆系统分析

**memory-python服务**功能：
- **短期记忆管理**：Redis Lists存储用户对话历史
- **上下文窗口**：默认20条消息的滑动窗口
- **记忆总结**：基于权重的自动总结机制（80%触发，60%压缩比例）
- **全局记忆**：虚拟主播共享所有用户的对话历史
- **过期清理**：24小时TTL + 定期清理任务

**现有限制**：
1. **缺乏结构化长期记忆**：仅基于时间序列的对话历史
2. **个性化不足**：无法记住用户的兴趣偏好和特征
3. **语义检索能力有限**：基于Redis Lists的简单查询
4. **关系建模缺失**：无法捕捉用户间和事件间的关系

## 2. Mem0框架优势

### 2.1 核心特性
- **多层级记忆**：用户级、会话级、代理级记忆管理
- **智能提取**：动态提取对话中的关键信息
- **语义检索**：基于向量的相似性搜索
- **自适应学习**：持续优化记忆存储和检索
- **高性能**：相比OpenAI Memory提升26%准确性，91%低延迟，90%少token使用

### 2.2 技术优势
- **生产就绪**：Apache 2.0许可，支持企业部署
- **多平台支持**：Python/JavaScript SDK
- **灵活集成**：支持各种LLM和向量数据库
- **扩展性强**：支持大规模并发用户

## 3. 集成架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Free-Agent-Vtuber                       │
│                    Enhanced Memory System                   │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Short-term    │    │   Long-term     │    │      AI         │
│   Memory        │◄──►│    Memory       │◄──►│   Processing    │
│ (Redis Lists)   │    │   (Mem0)        │    │  (chat-ai)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Context       │    │   Personalized  │    │   Enhanced      │
│   Window        │    │   Memory        │    │   Responses     │
│   (20 msgs)     │    │   Storage       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 3.2 混合记忆架构

采用**双层记忆系统**：

1. **短期记忆层（现有Redis系统）**
   - 保持现有实时对话上下文功能
   - 快速响应，低延迟
   - 临时缓存最近交互

2. **长期记忆层（新增Mem0系统）**
   - 存储用户偏好、兴趣、特征
   - 语义化记忆检索
   - 跨会话持久化

### 3.3 服务部署方案

#### 方案A：独立服务部署（推荐）
新增`long-term-memory-python`服务：

```yaml
# docker-compose.yml
long-term-memory:
  build:
    context: ./services/long-term-memory-python
    dockerfile: Dockerfile
  container_name: aivtuber-long-term-memory
  environment:
    - REDIS_HOST=${REDIS_HOST:-redis}
    - REDIS_PORT=${REDIS_PORT:-6379}
    - OPENAI_API_KEY=${OPENAI_API_KEY}
    - MEM0_CONFIG_PATH=/app/config/mem0_config.yaml
  volumes:
    - mem0_data:/app/data
    - ./services/long-term-memory-python/config:/app/config
  restart: unless-stopped
  depends_on:
    - redis
    - vector-db
```

#### 方案B：集成部署
扩展现有`memory-python`服务，添加Mem0功能。

**推荐方案A**，原因：
- 职责分离，易于维护
- 独立扩展和优化
- 降低现有系统风险
- 支持渐进式迁移

## 4. 数据流设计

### 4.1 增强的数据流

```
用户输入 → input-handler → user_input_queue
                                   ↓
                         ┌─────────┴──────────┐
                         ▼                    ▼
                   memory-python      long-term-memory
                 (短期记忆存储)         (长期记忆提取)
                         │                    │
                         ▼                    ▼
                 memory_updates ◄─────────┐   │
                         │                │   │
                         ▼                │   ▼
                   chat-ai ◄──────────────┴───┘
                 (上下文 + 长期记忆)
                         │
                         ▼
                 ai_responses → TTS → output
```

### 4.2 记忆更新流程

1. **输入处理**：
   ```
   用户消息 → memory-python存储 → 发布memory_updates事件
   ```

2. **长期记忆提取**：
   ```
   memory_updates → long-term-memory监听 → Mem0提取关键信息
   ```

3. **AI生成增强**：
   ```
   chat-ai收到memory_updates → 查询long-term-memory → 获取个性化上下文 → 生成回复
   ```

4. **记忆持久化**：
   ```
   AI回复 → long-term-memory存储 → 更新用户画像
   ```

## 5. 服务接口设计

### 5.1 长期记忆服务API

```python
class LongTermMemoryService:
    async def add_memory(self, user_id: str, content: str, metadata: dict) -> str
    async def search_memories(self, user_id: str, query: str, limit: int = 5) -> List[Dict]
    async def get_user_profile(self, user_id: str) -> Dict
    async def update_user_profile(self, user_id: str, updates: Dict) -> bool
    async def get_memory_stats(self, user_id: str) -> Dict
```

### 5.2 Redis消息格式

#### 长期记忆请求（ltm_requests队列）
```json
{
  "request_id": "req_1234567890",
  "type": "search|add|profile_get|profile_update",
  "user_id": "anonymous",
  "data": {
    "query": "用户查询文本",
    "content": "要存储的内容",
    "metadata": {"source": "conversation", "timestamp": "..."}
  }
}
```

#### 长期记忆响应（ltm_responses发布）
```json
{
  "request_id": "req_1234567890",
  "user_id": "anonymous",
  "memories": [
    {
      "content": "用户喜欢动漫",
      "metadata": {"category": "preference", "confidence": 0.8}
    }
  ],
  "user_profile": {"interests": ["动漫", "游戏"], "personality": "活泼"}
}
```

## 6. 技术实现细节

### 6.1 向量数据库选择

推荐使用**pgvector（PostgreSQL扩展）**：
- PostgreSQL + 向量扩展，部署简单
- ACID事务支持，数据可靠性高
- 与现有PostgreSQL基础设施集成良好
- 支持高效的向量相似性搜索和元数据过滤
- 比专用向量数据库更轻量级，维护成本低

```yaml
# docker-compose.yml添加
vector-db:
  image: pgvector/pgvector:pg16
  container_name: aivtuber-pgvector
  environment:
    POSTGRES_DB: long_term_memory
    POSTGRES_USER: ltm_user
    POSTGRES_PASSWORD: ltm_password
  ports:
    - "5432:5432"
  volumes:
    - pgvector_data:/var/lib/postgresql/data
  restart: unless-stopped
```

### 6.2 记忆分类系统

```python
MEMORY_CATEGORIES = {
    "preference": "用户偏好（喜欢的动漫、音乐等）",
    "personality": "性格特征（活泼、内向等）",
    "habit": "行为习惯（聊天时间、频率等）",
    "history": "重要事件（生日、纪念日等）",
    "context": "对话上下文（话题转换、情绪变化）"
}
```

### 6.3 记忆质量评估

```python
def evaluate_memory_quality(memory: Dict) -> float:
    """评估记忆的重要性和质量"""
    score = 0.0
    
    # 基于用户提及频率
    mention_count = memory.get("mention_count", 0)
    score += min(mention_count * 0.1, 1.0)
    
    # 基于情感强度
    emotion_intensity = memory.get("emotion_intensity", 0)
    score += emotion_intensity * 0.3
    
    # 基于时间衰减
    days_since = (datetime.now() - memory["created_at"]).days
    time_decay = max(0, 1 - days_since / 365)  # 1年完全衰减
    score *= time_decay
    
    return min(score, 1.0)
```

---

*本方案基于项目当前架构分析和Mem0框架特性设计，具体实施时可根据实际情况调整。*