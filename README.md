# Free-Agent-Vtuber 🤖🎙️

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
6.  [系统消息流与契约](#系统消息流与契约)
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

### 后端架构
* **核心架构**: 微服务 (Microservices), 事件驱动 (Event-Driven)
* **消息总线**: [Redis](https://redis.io/)
* **主要开发语言**: [Python 3.10+](https://www.python.org/) (用于初期模块开发)
* **AI 大语言模型**: 可插拔设计，支持各类 LLM API (e.g., OpenAI GPT series, Google Gemini, etc.)
* **语音合成 (TTS)**: 可插拔设计 (e.g., Edge-TTS, ElevenLabs, etc.)

### 前端界面
* **框架**: [Vue.js 3](https://vuejs.org/) - 现代化响应式前端框架
* **UI组件库**: [Vuetify 3](https://vuetifyjs.com/) - Material Design组件库
* **构建工具**: [Vite](https://vitejs.dev/) - 快速的前端构建工具
* **虚拟形象**: [Live2D](https://www.live2d.com/) - 2D虚拟角色动画技术
* **图标**: [Material Design Icons](https://materialdesignicons.com/)

### 管理与监控
* **本地开发管理**: [Flask](https://flask.palletsprojects.com/) - 轻量级Web管理界面（仅用于本地开发）
* **进程管理**: Python subprocess + psutil - 本地服务生命周期管理
* **实时监控**: WebSocket + 日志流 - 本地开发时的实时服务状态监控
* **生产部署**: Docker独立容器部署，无需集中管理器

### 虚拟形象驱动
* **VTube Studio**: [VTube Studio](https://store.steampowered.com/app/1325860/VTube_Studio/) (通过其API进行控制)

### 测试框架
* **测试框架**: [pytest](https://pytest.org/) + pytest-asyncio (支持异步测试)

## 系统消息流与契约

本项目采用 Redis 作为消息总线，服务通过队列（list）与频道（pub/sub）通信。自 2025-08 更新起，输入归一化统一由 input-handler 承担，并采用“B 模式：content 优先”。

- 端到端数据流（语音→文本→对话→TTS）
  1) 外部调用网关：POST /api/asr → 入队 asr_tasks（list）
  2) ASR 服务识别：消费 asr_tasks → 发布识别结果到 asr_results（pub/sub）
  3) 输入归一化：input-handler 订阅 asr_results，将 status=finished 的文本转为标准“用户输入任务”，LPUSH 到 user_input_queue（list）
  4) 记忆：memory 消费 user_input_queue，现已“优先使用 task_data.content，若无则回退读取 input_file”，成功后发布 memory_updates（pub/sub）
  5) 对话：chat-ai 订阅 memory_updates，生成回复，发布 ai_responses，同时 LPUSH tts_requests（list）
  6) 语音合成与输出：tts 消费 tts_requests，合成后发布到 task_response:{task_id}（pub/sub），output/gateway 呈现

- 关键通道与契约（摘录）
  - asr_results（频道，ASR → 全局）
    ResultMessage（简化）：{ task_id, status: "finished"|"failed"|"partial", text?, provider?, lang?, meta? }
    约束：status="finished" 时必须含 text；status="failed" 必须含 error
  - user_input_queue（队列，input-handler → memory）
    标准任务（content 优先）：
    {
      "task_id": "沿用上游，如 ASR task_id",
      "type": "text" | "audio",
      "user_id": "anonymous",
      "content": "识别文本（推荐）",
      "input_file": "/path/to/file (可选兜底)",
      "source": "asr" | "user" | "system",
      "timestamp": 1234567890,
      "meta": { "trace_id": "...", "lang": "zh", "from_channel": "asr_results", "provider": "fake|openai_whisper|funasr_local" }
    }
    行为：memory 现已优先读取 content；当 content 为空或不存在时，回退读取 input_file。
  - 其他：memory_updates（channel）、ai_responses（channel）、tts_requests（list）、task_response:{task_id}（channel）

- 启动顺序建议与验证
  1) Redis → gateway → asr → input-handler（启动时日志应出现“ASR bridge subscribed to channel: asr_results”）→ memory → chat-ai → tts → output
  2) curl /api/asr 发送任务，观察：
     - asr_results 有 finished 文本
     - input-handler 日志出现 Bridged ASR result to user_input_queue
     - memory 日志出现 Storing user text from content...
     - chat-ai/tts/output 按既有链路输出

注：后续将引入“结果持久化 + 查询接口”（GET /api/asr/{task_id}）和“上传/统一转码”能力，详见 docs/ 与模块 README。

## 快速开始 🚀

想要快速体验项目？我们提供两种部署方式：

### 🐳 Docker部署（推荐）

最简单的部署方式，一键启动所有服务：

```bash
# 1. 克隆项目
git clone https://github.com/your_username/AIVtuber.git
cd AIVtuber

# 2. 配置环境变量（模型服务商的url，应当在services/chat-ai-python和services/memory-python中的config.json配置。未来版本将支持url环境变量配置）
cp .env.example .env
# 编辑 .env 文件，设置您的 OPENAI_API_KEY 以及可选的 Redis 连接信息

# 3. 一键部署
# Linux/macOS:
chmod +x ./deploy.sh
./deploy.sh

# Windows:
deploy.bat

# 开发环境（支持热重载）:
docker compose -f docker-compose.dev.yml up -d
```

### 📦 本地部署

如果您希望本地开发或不使用Docker：

```bash
# 1. 克隆项目
git clone https://github.com/your_username/AIVtuber.git
cd AIVtuber

# 2. 启动Redis（如果未安装，请参考先决条件部分）
redis-server

# 3. 设置API密钥
export OPENAI_API_KEY=your_api_key_here

# 4. 启动管理器
cd manager
pip install -r requirements.txt
python app.py

# 5. 启动前端（新终端）
cd ../front_end
npm install
npm run dev
```

**访问地址：**
- 🎛️ **管理界面**: http://localhost:5000 - 管理所有微服务
- 🎭 **虚拟主播界面**: http://localhost:5173 - AI交互界面（本地启动）

## 开始使用

本项目目前设计为在本地环境中直接运行各个服务模块。

### 先决条件

根据您选择的部署方式，需要安装不同的软件：

#### 🐳 Docker部署（推荐）
* **Docker** - 容器运行环境
  - Windows: [Docker Desktop](https://www.docker.com/products/docker-desktop)
  - macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Linux: [Docker Engine](https://docs.docker.com/engine/install/)
* **Docker Compose** - 多容器编排工具（通常随Docker Desktop一起安装）

#### 📦 本地部署
* **Python 3.10 或更高版本** - 用于后端微服务开发
* **Node.js 16+ 和 npm** - 用于前端开发和构建
* **Redis Server** - 消息总线服务
  - macOS: `brew install redis`
  - Ubuntu/Debian: `sudo apt-get install redis-server`
  - Windows: 从 [Redis官网](https://redis.io/download) 下载安装
  - Docker: `docker run -d -p 6379:6379 redis:alpine`

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

本项目支持两种部署方式：Docker容器化部署和本地部署。

#### 🐳 方式一：Docker部署（推荐）

Docker部署是最简单、最可靠的部署方式，所有服务都运行在独立的容器中。

> 📖 **详细指南**: 查看 [Docker部署指南](docs/DOCKER.md) 了解完整的Docker使用说明

1.  **克隆仓库**
    ```bash
    git clone https://github.com/your_username/AIVtuber.git
    cd AIVtuber
    ```

2.  **配置环境变量**
    ```bash
    # 复制环境变量模板
    cp .env.example .env
    
    # 编辑 .env 文件，设置您的API密钥和可选的Redis配置
    # Windows: notepad .env
    # macOS/Linux: nano .env 或 vim .env
    ```
    
    在 `.env` 文件中设置：
    ```env
    # 必需：您的OpenAI API密钥
    OPENAI_API_KEY=your_actual_api_key_here

    # 可选：自定义Redis连接信息
    # 默认使用docker-compose内部的redis服务
    # 如果您想连接到外部Redis，请取消下面的注释并修改
    # REDIS_HOST=your_redis_host
    # REDIS_PORT=your_redis_port
    ```

3.  **一键部署**
    ```bash
    # Linux/macOS
    chmod +x deploy.sh
    ./deploy.sh
    
    # Windows
    deploy.bat
    ```

4.  **验证部署**
    ```bash
    # 查看所有服务状态
    docker-compose ps
    
    # 查看服务日志
    docker-compose logs -f
    ```

5.  **访问应用**
    - 🌐 **网关服务**: http://localhost:8000 - 微服务API网关
    - 🎭 **虚拟主播界面**: 需要单独启动前端（见下方说明）
    
    **注意**: Docker部署模式下，所有微服务独立运行，无集中管理界面。如需管理界面，请使用本地部署模式。

#### 📦 方式二：使用管理器（本地部署）

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

4.  **启动管理器**
    ```bash
    # 进入管理器目录
    cd manager

    # 创建并激活虚拟环境
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate

    # 安装依赖
    pip install -r requirements.txt

    # 启动管理器
    python app.py
    ```

5.  **访问管理界面**
    打开浏览器访问 `http://localhost:5000`，通过Web界面管理所有微服务的启动、停止和监控。

6.  **启动前端界面**
    ```bash
    # 新开终端，进入前端目录
    cd front_end

    # 安装Node.js依赖
    npm install

    # 启动开发服务器
    npm run dev
    ```
    前端将在 `http://localhost:5173` 启动，提供AI虚拟主播的交互界面。

#### 🔧 方式三：手动启动各服务

如果您希望手动管理各个服务：

1.  **设置并运行后端模块**
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

2.  **启动其他后端模块**
    打开新的终端窗口，重复步骤1来启动其他模块：
    - `memory-python` - 记忆管理模块
    - `input-handler-python` - 输入处理模块
    - `output-handler-python` - 输出处理模块
    - `tts-python` - 语音合成模块
    - `gateway-python` - 网关模块

3.  **启动前端**
    ```bash
    # 进入前端目录
    cd front_end

    # 安装依赖（首次运行）
    npm install

    # 启动开发服务器
    npm run dev
    ```

#### 服务端口说明

**本地部署模式：**
- **管理器**: `http://localhost:5000` - 服务管理界面（仅本地部署）
- **前端**: `http://localhost:5173` - AI虚拟主播交互界面
- **Redis**: `localhost:6379` - 消息总线

**Docker部署模式：**
- **网关服务**: `http://localhost:8000` - 微服务API网关
- **前端**: `http://localhost:5173` - AI虚拟主播交互界面（需单独启动）
- **Redis**: `localhost:6379` - 消息总线
- **各微服务**: 通过Redis进行通信，独立容器运行

## 开发与测试

本项目采用双环境架构，既保证了微服务的独立性，又提供了便捷的开发测试体验。

### 开发环境

项目包含后端Python环境和前端Node.js环境：

#### 后端开发环境

**生产环境** - 各服务独立部署：
```
services/
├── chat-ai-python/venv/      # AI服务独立环境
├── memory-python/venv/       # 记忆服务独立环境
└── ...                       # 其他服务独立环境
```

**开发环境** - 各服务独立开发：
每个服务模块都有自己的开发环境，可以独立进行开发和测试。要开发特定服务，请进入该服务目录并创建虚拟环境：

```bash
# 进入特定服务目录
cd services/chat-ai-python

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装服务依赖
pip install -r requirements.txt

# 如果需要运行测试，安装开发依赖
pip install -r ../../requirements-dev.txt
```

#### 前端开发环境

```bash
# 进入前端目录
cd front_end

# 安装依赖
npm install

# 开发模式（热重载）
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

**前端项目结构**：
```
front_end/
├── src/
│   ├── components/          # Vue组件
│   ├── assets/             # 静态资源
│   ├── live2d/             # Live2D相关文件
│   ├── composables/        # Vue组合式函数
│   ├── App.vue             # 主应用组件
│   └── main.js             # 应用入口
├── package.json            # 项目配置和依赖
├── vite.config.js          # Vite构建配置
└── index.html              # HTML模板
```

### 运行测试

每个服务模块都有独立的测试套件，使用 pytest 进行单元测试和集成测试：

```bash
# 进入特定服务目录
cd services/chat-ai-python

# 运行该服务的所有测试
pytest

# 运行特定类型的测试
pytest tests/unit/
pytest tests/integration/

# 运行特定测试文件
pytest tests/unit/test_ai_processor.py

# 运行测试并查看覆盖率
pytest --cov=. --cov-report=html

# 运行集成测试（需要Redis运行）
pytest tests/integration/ -v
```

**测试结构**（以 chat-ai-python 为例）：
```
services/chat-ai-python/tests/
├── unit/                     # 单元测试（使用模拟对象）
│   ├── test_ai_processor.py
│   ├── test_task_processor.py
│   └── test_config.py
├── integration/              # 集成测试（需要真实Redis）
│   └── test_redis_integration.py
└── conftest.py              # pytest配置
```

测试覆盖了：
- ✅ 各服务模块的核心逻辑
- ✅ Redis数据存储和检索
- ✅ 消息序列化/反序列化
- ✅ 错误处理和边界情况
- 🚧 更多服务模块测试持续开发中...

## 开发路线图

我们将分阶段构建 `AIVtuber`。

- [x] **Phase 0: 概念与架构设计** - 定义项目的核心原则和结构。
- [🚧] **Phase 1: 架构骨架验证 (The Backbone)** - 搭建核心通信链路，让两个本地模块通过 Redis 成功通信。
  - [x] 微服务架构搭建
  - [x] Redis消息总线集成
  - [x] 服务管理器开发
  - [x] 前端交互界面开发
  - [🚧] 服务间通信优化
- [ ] **Phase 2: 赋予"形体" (The Body)** - 让虚拟形象能够响应来自 Redis 的指令，做出简单动作。
  - [🚧] Live2D虚拟形象集成
  - [ ] VTube Studio API集成
  - [ ] 动作指令系统
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
**Free-Agent-Vtuber** - *An AI Soul in a Digital Shell.*
