# AIVtuber Docker 部署指南 🐳

本文档详细介绍如何使用Docker部署AIVtuber项目。

## 📋 目录

1. [架构概述](#架构概述)
2. [快速开始](#快速开始)
3. [开发环境](#开发环境)
4. [生产环境](#生产环境)
5. [故障排除](#故障排除)
6. [性能优化](#性能优化)

## 🏗️ 架构概述

### 容器架构

```
┌─────────────────────────────────────────────────────────────┐
│                    AIVtuber Docker 架构                      │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Nginx)     │  Manager (Flask)    │  Redis        │
│  Port: 3000          │  Port: 5000         │  Port: 6379   │
├─────────────────────────────────────────────────────────────┤
│  Gateway             │  Chat-AI            │  Memory       │
│  Port: 8000          │  Internal           │  Internal     │
├─────────────────────────────────────────────────────────────┤
│  Input-Handler       │  Output-Handler     │  TTS          │
│  Internal            │  Internal           │  Internal     │
└─────────────────────────────────────────────────────────────┘
```

### 服务说明

| 服务名 | 容器名 | 端口 | 描述 |
|--------|--------|------|------|
| frontend | aivtuber-frontend | 3000 | Vue.js前端界面 |
| manager | aivtuber-manager | 5000 | Flask管理界面 |
| redis | aivtuber-redis | 6379 | Redis消息总线 |
| gateway | aivtuber-gateway | 8000 | API网关服务 |
| chat-ai | aivtuber-chat-ai | - | AI聊天处理 |
| memory | aivtuber-memory | - | 记忆管理 |
| input-handler | aivtuber-input-handler | - | 输入处理 |
| output-handler | aivtuber-output-handler | - | 输出处理 |
| tts | aivtuber-tts | - | 语音合成 |

## 🚀 快速开始

### 1. 环境准备

确保已安装：
- Docker Desktop (Windows/macOS) 或 Docker Engine (Linux)
- Docker Compose

### 2. 部署步骤

```bash
# 克隆项目
git clone https://github.com/your_username/AIVtuber.git
cd AIVtuber

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置 OPENAI_API_KEY

# 一键部署
./deploy.sh  # Linux/macOS
# 或
deploy.bat   # Windows
```

### 3. 验证部署

```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 测试服务
curl http://localhost:5000  # 管理界面
curl http://localhost:3000  # 前端界面
```

## 🛠️ 开发环境

### 启动开发环境

```bash
# 启动开发环境（支持热重载）
docker-compose -f docker-compose.dev.yml up -d

# 查看开发环境状态
docker-compose -f docker-compose.dev.yml ps
```

### 开发环境特性

- **前端热重载**: 代码修改自动刷新
- **后端调试**: 支持断点调试
- **卷挂载**: 本地代码直接映射到容器
- **开发工具**: 包含开发所需的所有工具

### 开发工作流

```bash
# 1. 修改代码（本地编辑器）
# 2. 查看实时效果（浏览器自动刷新）
# 3. 查看日志
docker-compose -f docker-compose.dev.yml logs -f frontend-dev

# 4. 重启特定服务（如需要）
docker-compose -f docker-compose.dev.yml restart manager-dev
```

## 🏭 生产环境

### 生产部署配置

```bash
# 使用生产配置
docker-compose -f docker-compose.yml up -d

# 或使用环境变量
NODE_ENV=production docker-compose up -d
```

### 生产环境优化

1. **镜像优化**
   - 多阶段构建减小镜像大小
   - 使用Alpine Linux基础镜像
   - 清理不必要的依赖

2. **安全配置**
   - 非root用户运行
   - 最小权限原则
   - 安全头配置

3. **性能优化**
   - Nginx静态文件缓存
   - Gzip压缩
   - 健康检查配置

## 🔧 常用命令

### 服务管理

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启特定服务
docker-compose restart [服务名]

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f [服务名]
```

### 镜像管理

```bash
# 重新构建镜像
docker-compose build

# 强制重新构建
docker-compose build --no-cache

# 拉取最新镜像
docker-compose pull

# 清理未使用的镜像
docker image prune
```

### 数据管理

```bash
# 查看卷
docker volume ls

# 备份Redis数据
docker-compose exec redis redis-cli BGSAVE

# 查看容器内文件
docker-compose exec [服务名] ls -la
```

## 🐛 故障排除

### 常见问题

#### 1. 端口冲突

**问题**: `Port already in use`

**解决方案**:
```bash
# 查看端口占用
netstat -tulpn | grep :3000

# 修改docker-compose.yml中的端口映射
ports:
  - "3001:3000"  # 改为其他端口
```

#### 2. 内存不足

**问题**: 容器频繁重启

**解决方案**:
```bash
# 增加Docker内存限制
# Docker Desktop -> Settings -> Resources -> Memory

# 或在docker-compose.yml中限制内存使用
services:
  frontend:
    mem_limit: 512m
```

#### 3. 网络连接问题

**问题**: 服务间无法通信

**解决方案**:
```bash
# 检查网络
docker network ls
docker network inspect aivtuber-network

# 重新创建网络
docker-compose down
docker-compose up -d
```

#### 4. 环境变量问题

**问题**: API密钥未生效

**解决方案**:
```bash
# 检查环境变量
docker-compose exec chat-ai env | grep OPENAI

# 重新加载环境变量
docker-compose down
docker-compose up -d
```

### 调试技巧

```bash
# 进入容器调试
docker-compose exec [服务名] /bin/bash

# 查看容器资源使用
docker stats

# 查看详细日志
docker-compose logs --tail=100 -f [服务名]

# 检查健康状态
docker-compose ps
```

## ⚡ 性能优化

### 1. 镜像优化

```dockerfile
# 使用多阶段构建
FROM node:18-alpine AS builder
# ... 构建步骤

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

### 2. 缓存优化

```bash
# 利用Docker层缓存
# 先复制依赖文件，再复制源代码
COPY package*.json ./
RUN npm install
COPY . .
```

### 3. 资源限制

```yaml
services:
  frontend:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

### 4. 监控配置

```yaml
services:
  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
```

## 📊 监控和日志

### 日志管理

```bash
# 配置日志轮转
services:
  frontend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 监控指标

```bash
# 查看资源使用
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# 查看磁盘使用
docker system df
```

## 🔒 安全最佳实践

1. **使用非root用户**
2. **最小化镜像内容**
3. **定期更新基础镜像**
4. **使用secrets管理敏感信息**
5. **网络隔离**
6. **定期安全扫描**

```bash
# 安全扫描
docker scan [镜像名]
```

## 📚 参考资源

- [Docker官方文档](https://docs.docker.com/)
- [Docker Compose文档](https://docs.docker.com/compose/)
- [Docker最佳实践](https://docs.docker.com/develop/dev-best-practices/)
- [容器安全指南](https://docs.docker.com/engine/security/)

---

如有问题，请查看项目的[主要README](../README.md)或提交Issue。