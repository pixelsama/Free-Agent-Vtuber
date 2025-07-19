@echo off
REM AIVtuber Docker 部署脚本 (Windows)

echo 🚀 开始部署 AIVtuber...

REM 检查Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 未安装，请先安装 Docker Desktop
    pause
    exit /b 1
)

REM 检查Docker Compose
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose 未安装，请先安装 Docker Compose
    pause
    exit /b 1
)

REM 检查环境变量文件
if not exist .env (
    echo 📝 创建环境变量文件...
    copy .env.example .env
    echo ⚠️  请编辑 .env 文件，设置您的 OPENAI_API_KEY
    echo    然后重新运行此脚本
    pause
    exit /b 1
)

REM 检查API密钥
findstr "your_openai_api_key_here" .env >nul
if %errorlevel% equ 0 (
    echo ⚠️  请在 .env 文件中设置您的 OPENAI_API_KEY
    pause
    exit /b 1
)

echo 🔧 构建Docker镜像...
docker compose build

echo 🚀 启动服务...
docker compose up -d

echo ⏳ 等待服务启动...
timeout /t 10 /nobreak >nul

echo 🔍 检查服务状态...
docker compose ps

echo.
echo ✅ 微服务部署完成！
echo.
echo 🌐 网关服务: http://localhost:8000
echo.
echo ⚠️  前端需要单独启动：
echo    cd front_end
echo    npm install
echo    npm run dev
echo    前端将运行在: http://localhost:5173
echo.
echo 📊 查看日志: docker compose logs -f [服务名]
echo 🛑 停止服务: docker compose down
echo 🔄 重启服务: docker compose restart [服务名]
pause
