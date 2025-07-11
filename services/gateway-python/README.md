# AIVtuber API Gateway

WebSocket API网关服务，为前端提供统一的8000端口入口，自动路由到后端的input和output微服务。

## 功能特性

- **统一入口**: 前端只需连接8000端口
- **智能路由**: 根据路径自动路由到相应的后端服务
- **双向代理**: 完整的WebSocket双向消息转发
- **连接管理**: 实时跟踪和管理客户端连接
- **健康检查**: 提供服务状态监控
- **错误处理**: 完善的错误处理和日志记录

## 架构设计

```
前端 (WebSocket) → Gateway:8000 → Backend Services
                     ├── /ws/input → input-handler:8001
                     └── /ws/output/{task_id} → output-handler:8002
```

## 路由规则

### WebSocket端点
- `ws://localhost:8000/ws/input` → `ws://localhost:8001/ws/input`
- `ws://localhost:8000/ws/output/{task_id}` → `ws://localhost:8002/ws/output/{task_id}`

### HTTP端点  
- `GET /` - 网关状态页面
- `GET /health` - 健康检查
- `GET /connections` - 当前连接状态

## 安装和运行

1. **安装依赖**
```bash
cd services/gateway-python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **启动后端服务**
```bash
# 终端1: 启动input-handler
cd services/input-handler-python
python main.py  # 运行在8001端口

# 终端2: 启动output-handler  
cd services/output-handler-python
python main.py  # 运行在8002端口
```

3. **启动网关**
```bash
# 终端3: 启动gateway
cd services/gateway-python
python main.py  # 运行在8000端口
```

## 工作流程

1. **前端连接** → WebSocket连接到8000端口
2. **路由识别** → 根据路径确定目标后端服务
3. **后端连接** → 网关连接到相应的后端服务
4. **双向代理** → 透明转发所有WebSocket消息
5. **连接管理** → 跟踪连接状态，处理断开

## 代理特性

### 消息转发
- **文本消息**: 完整转发JSON格式消息
- **二进制消息**: 透明转发音频等二进制数据
- **元数据保持**: 保持消息的完整性和顺序

### 错误处理
- **连接超时**: 自动检测和处理连接超时
- **后端不可用**: 优雅处理后端服务离线
- **客户端断开**: 及时清理资源和连接

### 日志记录
- **连接跟踪**: 记录每个连接的建立和断开
- **消息转发**: 记录消息转发的方向和状态
- **错误诊断**: 详细的错误信息和调试日志

## 配置

主要配置在 `config.json` 中：

- 网关服务器设置
- 后端服务URL配置
- 代理连接参数
- 超时和限制设置

## 监控和调试

### 健康检查
```bash
curl http://localhost:8000/health
```

### 连接状态
```bash  
curl http://localhost:8000/connections
```

### 网关状态页面
浏览器访问: `http://localhost:8000`

## 部署建议

### 开发环境
按照上述步骤依次启动三个服务即可。

### 生产环境
- 使用进程管理器(如PM2、systemd)管理服务
- 配置负载均衡和健康检查
- 启用日志轮转和监控告警

## 故障排除

### 常见问题
1. **后端服务不可用**: 检查input-handler和output-handler是否正常运行
2. **端口冲突**: 确保8000、8001、8002端口未被占用
3. **连接超时**: 检查网络连接和防火墙设置

### 调试模式
启动时添加详细日志：
```bash
python main.py --log-level debug
```

## 文件结构

```
gateway-python/
├── main.py              # 主程序
├── requirements.txt     # 依赖包
├── config.json         # 配置文件
└── README.md           # 说明文档
```