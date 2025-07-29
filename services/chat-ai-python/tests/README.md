# Chat AI Python 模块测试说明

## 测试结构

```
tests/
├── conftest.py          # 单元测试共享fixtures
├── unit/                # 单元测试
│   ├── __init__.py
│   ├── test_ai_processor.py    # AI处理器测试
│   ├── test_task_processor.py  # 任务处理器测试
│   └── test_config.py          # 配置加载测试
└── integration/         # 集成测试
    ├── __init__.py
    ├── conftest.py             # 集成测试共享fixtures
    └── test_redis_integration.py  # Redis集成测试
```

## 运行测试

### 运行所有测试

```bash
# 在chat-ai-python目录下运行
pytest

# 或者运行特定类型的测试
pytest tests/unit/
pytest tests/integration/
```

### 运行特定测试

```bash
# 运行特定测试文件
pytest tests/unit/test_ai_processor.py

# 运行特定测试类
pytest tests/unit/test_ai_processor.py::TestAIProcessor

# 运行特定测试方法
pytest tests/unit/test_ai_processor.py::TestAIProcessor::test_process_with_rules_greeting
```

### 测试选项

```bash
# 详细输出
pytest -v

# 显示测试执行过程
pytest -s

# 生成覆盖率报告
pytest --cov=services/chat_ai_python --cov-report=html

# 并行运行测试
pytest -n auto
```

## 测试环境要求

1. **Redis服务器**：集成测试需要Redis服务器运行在localhost:6379
2. **Python依赖**：确保已安装开发依赖：
   ```bash
   pip install -r requirements.txt
   pip install -r ../../requirements-dev.txt
   ```

## 测试类型说明

### 单元测试 (Unit Tests)

单元测试主要测试各个组件的独立功能：

- **AIProcessor测试**：测试AI处理逻辑，包括规则回复和AI回复
- **TaskProcessor测试**：测试任务处理逻辑，包括Redis交互
- **配置测试**：测试配置文件加载和验证

### 集成测试 (Integration Tests)

集成测试验证组件之间的交互：

- **Redis集成**：测试与Redis服务器的连接和数据操作
- **消息流测试**：测试完整的消息处理流程

## 测试覆盖率

目标测试覆盖率达到80%以上，包括：

1. 正常流程测试
2. 异常处理测试
3. 边界条件测试
4. 配置变化测试

## 编写新测试

1. 在相应的测试目录中创建测试文件
2. 使用pytest框架和asyncio支持
3. 利用现有的fixtures减少重复代码
4. 遵循现有的测试命名约定
5. 确保测试的独立性和可重复性
