#!/bin/bash

echo "🚀 启动 AIVtuber 服务管理器..."

# 进入manager目录
cd "$(dirname "$0")"

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "🐍 激活manager虚拟环境..."
    source .venv/bin/activate
    PYTHON_CMD="python"
    PIP_CMD="pip"
else
    echo "⚠️  未找到manager虚拟环境，使用系统Python"
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
fi

# 检查Python环境
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "❌ Python未安装或虚拟环境配置有误"
    exit 1
fi

# 安装依赖
echo "📦 安装依赖包..."
$PIP_CMD install -r requirements.txt

# 启动Flask应用
echo "🌐 启动Web服务 (http://localhost:5000)..."
echo "💡 按 Ctrl+C 停止服务"
echo "📱 在浏览器中访问: http://localhost:5000"
echo "----------------------------------------"

# 启动应用并保持终端
$PYTHON_CMD app.py

# 如果应用退出，保持终端打开
echo ""
echo "⚠️  服务已停止"
echo "💬 按任意键退出..."
read -n 1