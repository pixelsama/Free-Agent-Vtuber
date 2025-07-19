#!/bin/bash

# AIVtuber Docker 部署脚本

set -e

echo "🚀 开始部署 AIVtuber..."

# 检查Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 插件未正确安装或无法工作，请检查 Docker 安装"
    exit 1
fi

# 检查环境变量文件
if [ ! -f .env ]; then
    echo "📝 创建环境变量文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，设置您的 OPENAI_API_KEY"
    echo "   然后重新运行此脚本"
    exit 1
fi

# 检查API密钥
if grep -q "your_openai_api_key_here" .env; then
    echo "⚠️  请在 .env 文件中设置您的 OPENAI_API_KEY"
    exit 1
fi

echo "🔧 构建Docker镜像..."
docker compose build

echo "🚀 启动服务..."
docker compose up -d

echo "⏳ 等待服务启动..."
sleep 10

echo "🔍 检查服务状态..."
docker compose ps

echo ""
echo "✅ 部署完成！"
echo ""
echo "🎛️  管理界面: http://localhost:5000"
echo "🎭 虚拟主播界面: http://localhost:3000"
echo ""
echo "📊 查看日志: docker compose logs -f [服务名]"
echo "🛑 停止服务: docker compose down"
echo "🔄 重启服务: docker compose restart [服务名]"
