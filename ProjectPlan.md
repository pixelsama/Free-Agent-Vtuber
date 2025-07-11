### **AIVtuber 项目启动计划 (Project Kick-off Plan)**

  * **项目代号**: `AIVtuber`
  * **最后更新**: 2025年7月11日, 12:07 PM JST
  * **核心愿景**: 构建一个基于事件驱动架构、支持多语言模块、可灵活扩展的 AI 虚拟主播。

#### **核心设计原则**

1.  **事件驱动 (Event-Driven)**: 所有模块通过 Redis 消息总线进行通信，实现高度解耦。
2.  **技术异构 (Polyglot)**: 架构支持使用不同语言编写的模块，但初期我们以 Python 为起点快速验证。
3.  **增量开发 (Incremental)**: 严格遵循“先骨架 -\> 再形体 -\> 后灵魂”的顺序，分阶段实现，每个阶段都有可验证的成果。

-----

### **开发路线图 (Development Roadmap)**

在您按照我们讨论的结果，创建了如下的项目目录结构之后：

```
AIVtuber/
└── services/
    └── ... (各个模块的目录)
```

我们将开始以下四个核心阶段的开发。

#### **Phase 1: 架构骨架验证 (The Backbone)**

  * **本阶段目标**: **证明核心通信链路畅通。** 让两个独立的本地 Python 模块通过 Redis 成功交换信息。这是整个项目的基石。

  * **涉及模块**: `services/input-cli`, `services/worker-test`

  * **开发步骤**:

    1.  **确认 Redis 运行**: 在终端运行 `redis-cli ping`，确保得到 `PONG`。
    2.  **创建 `input-cli` 模块**:
          * 在 `services/` 下创建 `input-cli/` 目录。
          * 在 `input-cli/` 中建立独立的 Python 虚拟环境 (`venv`) 并安装 `redis`。
          * 编写 `main.py`，功能是：接收用户在命令行的输入，并使用 `LPUSH` 将输入内容推送到 Redis 的一个列表（例如 `aivtuber:tasks`）中。
    3.  **创建 `worker-test` 模块**:
          * 在 `services/` 下创建 `worker-test/` 目录。
          * 同样，在 `worker-test/` 中建立独立的 Python 虚拟环境并安装 `redis`。
          * 编写 `main.py`，功能是：使用 `BRPOP` 阻塞式地监听 `aivtuber:tasks` 列表，一旦收到消息，就在终端打印出来。
    4.  **联调测试**:
          * 打开两个终端。
          * 终端A：进入 `input-cli` 目录，激活环境，运行 `python main.py`。
          * 终端B：进入 `worker-test` 目录，激活环境，运行 `python main.py`。
          * 在终端A中输入任意文字并回车，观察终端B是否立即打印出相同内容。

  * **完成标志**: **测试成功。** 这证明了您的事件驱动架构的基础是可靠的。

-----

#### **Phase 2: 赋予“形体” (The Body)**

  * **本阶段目标**: **让虚拟形象响应指令。** 将 `worker-test` 升级为能控制 VTube Studio 的模块。

  * **涉及模块**: `services/input-cli`, `services/vtuber-io`

  * **开发步骤**:

    1.  **准备虚拟形象**:
          * 安装并运行 VTube Studio。
          * 加载一个模型（自带或免费示例模型均可）。
          * 在设置中**开启 API**，并记下 IP 和端口。
    2.  **创建 `vtuber-io` 模块**:
          * 将 `worker-test` 目录重命名或复制为 `vtuber-io`。
          * 在其虚拟环境中，安装 VTube Studio 的 Python API 库（例如 `pyvts`）。
    3.  **编写控制逻辑**:
          * 修改 `vtuber-io` 的 `main.py`。
          * 在程序启动时，初始化并连接到 VTube Studio API。
          * 在 `while` 循环中，当从 Redis 收到特定指令（例如，一个内容为 `{"action": "smile"}` 的 JSON 字符串）时，调用 `pyvts` 库的相应函数来触发模型的某个动作或表情（例如，触发一个“微笑”的热键）。
    4.  **联调测试**:
          * 运行 `vtuber-io` 模块。
          * 在另一个终端，使用 `redis-cli` 或 `input-cli` 模块向 `aivtuber:tasks` 推送指令，例如：
            `LPUSH aivtuber:tasks '{"action": "smile"}'`
          * 观察屏幕上的虚拟形象是否做出了相应动作。

  * **完成标志**: **您可以通过 Redis 发送指令，精确控制虚拟形象做出简单动作。**

-----

#### **Phase 3: 注入“智能” (The Brain)**

  * **本阶段目标**: **让 Agent 能够思考。** 引入大语言模型（LLM）来处理对话。

  * **涉及模块**: `services/chat-ai`, `services/vtuber-io`

  * **开发步骤**:

    1.  **获取 LLM API**:
          * 选择一个 LLM 服务商（如 OpenAI, Google Gemini 等），注册并获取 API Key。
    2.  **创建 `chat-ai` 模块**:
          * 在 `services/` 下创建 `chat-ai/` 目录，并配置好其独立的 Python 环境。
          * 安装 `redis` 和所选 LLM 的 `sdk`（例如 `openai`）。
    3.  **编写对话逻辑**:
          * `chat-ai` 的 `main.py` 监听一个新的 Redis 列表，例如 `aivtuber:requests:chat`。
          * 收到用户发来的文本后，构造一个合适的 Prompt（例如，“你是一个可爱的虚拟主播，请回答以下问题：...”），然后调用 LLM API。
          * **【架构关键点】** 获取到 LLM 返回的文本后，`chat-ai` 模块**不直接**控制任何东西。它将结果处理成一个标准的“动作指令”，然后推送到另一个 Redis 列表，例如 `aivtuber:actions`。
            `LPUSH aivtuber:actions '{"action": "speak", "payload": {"text": "你好呀，很高兴认识你！"}}'`
    4.  **联调测试**:
          * 运行 `chat-ai` 模块。
          * 使用 `redis-cli` 向 `aivtuber:requests:chat` 推送一个问题。
          * 使用 `redis-cli` 的 `BRPOP aivtuber:actions 0` 来查看 `chat-ai` 模块是否成功生成了“动作指令”。

  * **完成标志**: **系统能够将一个自然语言问题，转化为一个结构化的、可执行的“动作指令”。**

-----

#### **Phase 4: 赋予“声音” (The Voice)**

  * **本阶段目标**: **让 Agent 开口说话。** 让 `vtuber-io` 模块能够执行 `speak` 动作。

  * **涉及模块**: `services/vtuber-io`

  * **开发步骤**:

    1.  **选择 TTS 引擎**:
          * 选择一个语音合成方案。可以是离线库（如 `pyttsx3`），也可以是效果更好的在线 API（如 `edge-tts`, `ElevenLabs` API 等）。
    2.  **升级 `vtuber-io` 模块**:
          * 在其虚拟环境中安装所选的 TTS 库。
          * 修改 `main.py`，让它除了监听 `aivtuber:tasks`，也开始监听 `aivtuber:actions`。
    3.  **实现 `speak` 动作**:
          * 当从 `aivtuber:actions` 收到 `{"action": "speak", ...}` 指令时：
            a.  提取 `text` 负载。
            b.  调用 TTS 引擎，将文本转换为一个音频文件（例如 `response.mp3`）。
            c.  调用 VTube Studio API，让它播放这个音频文件，并同时自动匹配口型动画（VTube Studio 支持此功能）。
    4.  **端到端测试**:
          * 依次启动 `vtuber-io` 和 `chat-ai` 模块。
          * 使用 `redis-cli` 向 `aivtuber:requests:chat` 推送一个问题。
          * 观察并倾听您的 VTuber 是否能用 AI 生成的内容、流畅地开口说话。

  * **完成标志**: **您的 `AIVtuber` MVP (最小可行产品) 诞生了！**

-----

### **未来展望 (Future Enhancements)**

当 MVP 完成后，您就可以在这个坚实的架构上，像搭积木一样添加更多激动人心的功能了：

  * **长期记忆模块**: 引入数据库（如 `PostgreSQL`, `MongoDB`）来记录对话历史。
  * **情感感知模块**: 分析文本情感，让 VTuber 做出对应的表情。
  * **视觉模块**: 引入计算机视觉库（如 `OpenCV`），让 Agent 能“看到”屏幕内容或摄像头画面。
  * **工具使用模块**: 让 Agent 能够调用外部 API（如查询天气、搜索网页）。