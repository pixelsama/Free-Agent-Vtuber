# AIVtuber 🤖🎙️

![Project Status](https://img.shields.io/badge/status-in%20development-blue)
![License](https://img.shields.io/badge/license-MIT-green)

一个基于事件驱动架构、可灵活扩展的 AI 虚拟主播项目。

---

## 目录

1.  [关于项目](#关于项目)
2.  [技术栈](#技术栈)
3.  [开始使用](#开始使用)
    * [先决条件](#先决条件)
    * [环境配置](#环境配置)
    * [安装与运行](#安装与运行)
4.  [开发与测试](#开发与测试)
    * [开发环境](#开发环境)
    * [运行测试](#运行测试)
5.  [开发路线图](#开发路线图)
6.  [参与贡献](#参与贡献)
7.  [许可证](#许可证)

## 关于项目

`AIVtuber` 是一个个人实验项目，旨在探索构建一个真正由 AI 驱动、能够进行实时交互的虚拟主播。

本项目的核心特点在于其**架构**：

* **事件驱动 (Event-Driven)**: 整个系统通过一个中心化的消息总线（Redis）进行通信，各个功能模块高度解耦，互不直接依赖。
* **技术异构 (Polyglot)**: 架构允许使用任何编程语言来开发功能模块，只要该语言能与 Redis 交互。这使得我们可以为不同的任务选择最合适的工具。
* **可扩展性 (Scalable)**: 得益于解耦设计，可以像搭积木一样轻松地为 Agent 添加新功能（如长期记忆、视觉感知、工具使用等），而无需修改现有模块。

我们的目标不仅仅是创建一个单一的 AI 主播，而是构建一个能够持续进化、集成社区力量的、强大的 AI Agent 框架。

## 技术栈

* **核心架构**: 微服务 (Microservices), 事件驱动 (Event-Driven)
* **消息总线**: [Redis](https://redis.io/)
* **主要开发语言**: [Python 3.10+](https://www.python.org/) (用于初期模块开发)
* **虚拟形象驱动**: [VTube Studio](https://store.steampowered.com/app/1325860/VTube_Studio/) (通过其API进行控制)
* **AI 大语言模型**: 可插拔设计，支持各类 LLM API (e.g., OpenAI GPT series, Google Gemini, etc.)
* **语音合成 (TTS)**: 可插拔设计 (e.g., Edge-TTS, ElevenLabs, etc.)
* **测试框架**: [pytest](https://pytest.org/) + pytest-asyncio (支持异步测试)

## 开始使用

本项目目前设计为在本地环境中直接运行各个服务模块。

### 先决条件

在开始之前，请确保您的开发环境中已安装以下软件：

* Python 3.10 或更高版本
* Redis Server (可以通过 `brew install redis`, `sudo apt-get install redis-server` 或从官网下载安装)

### 环境配置

#### AI API 配置

本项目支持 OpenAI 兼容的 API，需要配置 API 密钥：

```bash
# 设置 OpenAI API 密钥（必需）
export OPENAI_API_KEY=your_api_key_here
```

**支持的 API 提供商：**
- OpenAI GPT 系列
- Google Gemini (通过 OpenAI 兼容接口)
- 其他 OpenAI 兼容的 API 服务

**API 密钥配置方式：**
1. **环境变量（推荐）**: 设置 `OPENAI_API_KEY` 环境变量
2. **配置文件**: 在各服务的 `config.json` 中的 `ai.api_key` 字段设置

系统会优先使用环境变量，如果未设置则回退到配置文件。

### 安装与运行

1.  **克隆仓库**
    ```bash
    git clone https://github.com/your_username/AIVtuber.git
    cd AIVtuber
    ```

2.  **启动核心服务**
    确保您的本地 Redis 服务正在运行。
    ```bash
    redis-cli ping
    # 应该返回 PONG
    ```

3.  **设置环境变量**
    ```bash
    # 设置 AI API 密钥
    export OPENAI_API_KEY=your_actual_api_key_here
    ```

4.  **设置并运行模块**
    本项目的所有模块都存放在 `services/` 目录下。您需要为每个模块单独设置环境并运行。

    以 `chat-ai-python` 模块为例：
    ```bash
    # 1. 进入模块目录
    cd services/chat-ai-python

    # 2. 创建并激活Python虚拟环境
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate

    # 3. 安装依赖
    pip install -r requirements.txt

    # 4. 运行模块 (此终端将保持运行状态)
    python main.py
    ```

5.  **启动其他模块**
    打开新的终端窗口，重复步骤4来启动其他模块（如 `memory-python`, `input-handler-python` 等）。每个模块都在自己的终端中独立运行。

## 开发与测试

本项目采用双环境架构，既保证了微服务的独立性，又提供了便捷的开发测试体验。

### 开发环境

项目包含两套Python环境：

**生产环境** - 各服务独立部署：
```
services/
├── chat-ai-python/venv/      # AI服务独立环境
├── memory-python/venv/       # 记忆服务独立环境
└── ...                       # 其他服务独立环境
```

**开发环境** - 统一开发测试：
```bash
# 1. 创建开发环境（项目根目录）
python3 -m venv dev-venv
source dev-venv/bin/activate

# 2. 安装开发依赖（包含所有服务依赖 + 测试工具）
pip install -r requirements-dev.txt
```

### 运行测试

我们使用 pytest 进行单元测试和集成测试：

```bash
# 激活开发环境
source dev-venv/bin/activate

# 运行所有测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/unit/test_memory_manager.py -v

# 运行测试并查看覆盖率
pytest tests/ --cov=services --cov-report=html

# 运行集成测试（需要Redis运行）
pytest tests/integration/ -v
```

**测试结构**：
```
tests/
├── unit/                     # 单元测试（使用模拟对象）
│   └── test_memory_manager.py
├── integration/              # 集成测试（需要真实Redis）
│   └── test_redis_flow.py
├── fixtures/                 # 测试数据
│   └── sample_messages.json
└── conftest.py              # pytest配置
```

测试覆盖了：
- ✅ 记忆管理模块的核心逻辑
- ✅ Redis数据存储和检索
- ✅ 消息序列化/反序列化
- ✅ 错误处理和边界情况
- 🚧 更多服务模块测试开发中...

## 开发路线图

我们将分阶段构建 `AIVtuber`。

- [x] **Phase 0: 概念与架构设计** - 定义项目的核心原则和结构。
- [🚧] **Phase 1: 架构骨架验证 (The Backbone)** - 搭建核心通信链路，让两个本地模块通过 Redis 成功通信。
- [ ] **Phase 2: 赋予"形体" (The Body)** - 让虚拟形象能够响应来自 Redis 的指令，做出简单动作。
- [ ] **Phase 3: 注入"智能" (The Brain)** - 集成大语言模型，让 Agent 能够"思考"并生成对话内容。
- [ ] **Phase 4: 赋予"声音" (The Voice)** - 集成 TTS 引擎，让 Agent 能够开口说话，完成 MVP。

#### 未来展望

* [ ] **长期记忆模块**: 集成数据库，让 Agent 拥有记忆。
* [ ] **情感感知模块**: 通过文本分析赋予 Agent 情感表达能力。
* [ ] **视觉感知模块**: 让 Agent 能够"看到"屏幕或摄像头。
* [ ] **工具使用模块**: 允许 Agent 调用外部 API（天气、搜索等）。

## 参与贡献

我们欢迎任何形式的贡献！如果您有好的想法或建议，请随时提出 Issue 或提交 Pull Request。

1.  Fork 本项目
2.  创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  打开一个 Pull Request

## 许可证

本项目采用 MIT 许可证。详情请见 `LICENSE` 文件。

---
**AIVtuber** - *An AI Soul in a Digital Shell.*