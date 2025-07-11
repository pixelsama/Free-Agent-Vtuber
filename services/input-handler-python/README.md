# AIVtuber Input Handler

专门负责用户输入处理的WebSocket服务模块，基于事件驱动架构设计。

## 功能特性

- **纯输入处理**: 专注于接收和处理用户输入，不处理输出
- **多格式支持**: 支持文本和音频(WebM/Opus)输入
- **分块传输**: 支持大文件的分块上传
- **Redis集成**: 通过Redis事件总线发送任务到AI处理模块
- **任务管理**: 自动生成task_id，跟踪处理状态
- **错误处理**: 完善的错误处理和日志记录

## 接口端点

### 输入WebSocket
- **端点**: `ws://localhost:8000/ws/input`
- **功能**: 接收用户输入数据(文本/音频)
- **流程**: 连接 → 获取task_id → 上传数据 → 确认处理

## 工作流程

1. **客户端连接** → WebSocket `/ws/input`
2. **分配任务ID** → 返回唯一的task_id
3. **数据上传** → 分块接收文本或音频数据
4. **保存文件** → 存储到临时目录 `/tmp/aivtuber_tasks/{task_id}/`
5. **Redis推送** → 发送任务到 `user_input_queue` 队列
6. **确认处理** → 返回处理状态给客户端

## 安装和运行

1. **安装依赖**
```bash
cd services/input-handler-python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **启动Redis**
```bash
redis-server
```

3. **运行模块**
```bash
python main.py
```

服务将启动在 `http://localhost:8000`

## Redis集成

### 输入队列
- **队列名**: `user_input_queue`
- **消息格式**:
```json
{
    "task_id": "uuid-string",
    "type": "text|audio", 
    "input_file": "/tmp/aivtuber_tasks/{task_id}/input.txt",
    "timestamp": 1641234567.89
}
```

## 配置

主要配置在 `config.json` 中：

- WebSocket输入端点设置
- 文件上传限制
- Redis连接参数
- 临时文件存储路径

## 与其他模块集成

此模块作为整个AIVtuber系统的输入网关：

1. 接收前端用户输入
2. 通过Redis队列发送给AI处理模块
3. AI处理模块通过其他方式将结果返回给前端

其他模块可以订阅 `user_input_queue` 队列来处理用户输入。

## 文件结构

```
input-handler-python/
├── main.py              # 主程序
├── requirements.txt     # 依赖包
├── config.json         # 配置文件
├── README.md           # 说明文档
└── 接口文档.md         # 详细接口文档
```