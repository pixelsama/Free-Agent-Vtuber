# Free-Agent-Vtuber 🤖🎙️

![Project Status](https://img.shields.io/badge/status-in%20development-blue)
![License](https://img.shields.io/badge/license-MIT-green)

一个基于事件驱动架构、可灵活扩展的 AI 虚拟主播项目。

## 目录

1. [关于项目](#关于项目)
2. [技术栈](#技术栈)
3. [快速开始](#快速开始)
4. [开发与测试](#开发与测试)
5. [系统消息流与契约](#系统消息流与契约)
6. [开发路线图](#开发路线图)
7. [参与贡献](#参与贡献)
8. [许可证](#许可证)

## 关于项目

`Free-Agent-Vtuber` 是一个个人实验项目，旨在探索构建一个真正由 AI 驱动、能够进行实时交互的虚拟主播。

本项目的核心特点在于其 **架构**：

* **事件驱动 (Event-Driven)**：整个系统通过中心化的消息总线（Redis）进行通信，各个功能模块高度解耦。
* **技术异构 (Polyglot)**：架构允许使用任何编程语言，只要该语言能与 Redis 交互。
* **可扩展性 (Scalable)**：得益于解耦设计，可以像搭积木一样添加新功能（如长期记忆、视觉感知、工具使用等）。

目标不仅是创建一个单一的 AI 主播，而是构建一个能够持续进化的强大 AI Agent 框架。

## 技术栈

### 后端架构
* **核心架构**：微服务，事件驱动
* **消息总线**：[Redis](https://redis.io/)
* **主要开发语言**：[Python 3.10+](https://www.python.org/)
* **AI 大语言模型**：可插拔设计，支持各类 LLM API（如 OpenAI GPT、Google Gemini 等）
* **语音合成 (TTS)**：可插拔设计（如 Edge-TTS、ElevenLabs 等）

### 前端界面
* **框架**：[Vue.js 3](https://vuejs.org/)
* **UI 组件库**：[Vuetify 3](https://vuetifyjs.com/)
* **构建工具**：[Vite](https://vitejs.dev/)
* **虚拟形象**：[Live2D](https://www.live2d.com/)

### 管理与监控
* **本地开发管理**：[Flask](https://flask.palletsprojects.com/) - 轻量级 Web 管理界面
* **进程管理**：Python subprocess + psutil - 本地服务生命周期管理
* **实时监控**：WebSocket + 日志流 - 本地开发时的实时服务状态监控
* **生产部署**：Docker 独立容器部署

### 测试框架
* **测试框架**：[pytest](https://pytest.org/) + pytest-asyncio

## 快速开始

### 先决条件
* [Docker](https://www.docker.com/) & Docker Compose
* [Node.js 18+](https://nodejs.org/)
* [Python 3.10+](https://www.python.org/)（用于本地工具）

### 克隆项目

```bash
git clone https://github.com/your_username/Free-Agent-Vtuber.git
cd Free-Agent-Vtuber
cp .env.example .env
```

### Docker 一键启动

```bash
docker compose up -d
# 或者开发环境热重载
# docker compose -f docker-compose.dev.yml up
```

### Manager（可选）

```bash
bash manager/start.sh
```

访问 http://localhost:5000 管理服务。

### 前端开发

```bash
cd front_end
npm install
npm run dev
```

## 开发与测试

### 开发环境

```bash
pip install -r requirements-dev.txt
```

### 运行测试

每个服务模块都有独立测试套件，进入对应服务目录运行：

```bash
cd services/<service>
pytest -q
```

## 系统消息流与契约

本项目采用 Redis 作为消息总线，服务通过队列（list）与频道（pub/sub）通信。输入归一化由 `input-handler` 负责，采用 “content 优先” 的策略。

端到端数据流（语音 → 文本 → 对话 → TTS）：

1. 外部调用网关：POST `/api/asr` → 入队 `asr_tasks`（list）
2. ASR 服务识别：消费 `asr_tasks` → 发布识别结果到 `asr_results`（pub/sub）
3. 输入归一化：`input-handler` 订阅 `asr_results`，将 `status=finished` 的文本转为标准用户输入任务，`LPUSH` 到 `user_input_queue`（list）
4. 记忆：`memory` 消费 `user_input_queue`，优先使用 `task_data.content`，成功后发布 `memory_updates`（pub/sub）
5. 对话：`chat-ai` 订阅 `memory_updates`，生成回复，发布 `ai_responses`，并 `LPUSH tts_requests`（list）
6. 语音合成与输出：`tts` 消费 `tts_requests`，合成后发布到 `task_response:{task_id}`（pub/sub），`output`/`gateway` 呈现

## 开发路线图

我们将分阶段构建 `Free-Agent-Vtuber`：

- [x] **Phase 0: 概念与架构设计** - 定义项目的核心原则和结构
- [🚧] **Phase 1: 架构骨架验证 (The Backbone)**
  - [x] 微服务架构搭建
  - [x] Redis 消息总线集成
  - [x] 服务管理器开发
  - [x] 前端交互界面开发
  - [🚧] 服务间通信优化
- [ ] **Phase 2: 赋予 "形体" (The Body)**
  - [🚧] Live2D 虚拟形象集成
  - [ ] VTube Studio API 集成
  - [ ] 动作指令系统
- [ ] **Phase 3: 注入 "智能" (The Brain)** - 集成大语言模型
- [ ] **Phase 4: 赋予 "声音" (The Voice)** - 集成 TTS 引擎，完成 MVP

#### 未来展望

* [ ] **长期记忆模块**：集成数据库，让 Agent 拥有记忆
* [ ] **情感感知模块**：通过文本分析赋予 Agent 情感表达能力
* [ ] **视觉感知模块**：让 Agent 能够 "看到" 屏幕或摄像头
* [ ] **工具使用模块**：允许 Agent 调用外部 API（天气、搜索等）

## 参与贡献

我们欢迎任何形式的贡献！

1. Fork 本项目
2. 创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'feat: add AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## 许可证

本项目采用 MIT 许可证。详情请见 `LICENSE` 文件。

---
**Free-Agent-Vtuber** - *An AI Soul in a Digital Shell.*

