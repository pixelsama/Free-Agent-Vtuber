# 前端本地开发指南

前端已从Docker化部署中移除，现在只能在本地运行。

## 环境要求

- Node.js (推荐版本 16+)
- npm 或 yarn

## 安装依赖

```bash
cd front_end
npm install
```

## 本地开发

启动开发服务器（支持热重载）：

```bash
npm run dev
```

默认运行在 http://localhost:5173

## 生产构建

构建生产版本：

```bash
npm run build
```

预览生产构建：

```bash
npm run preview
```

## 注意事项

- 确保后端服务正在运行（通过Docker Compose启动）
- 前端会连接到本地的后端API服务
- 开发时修改代码会自动热重载