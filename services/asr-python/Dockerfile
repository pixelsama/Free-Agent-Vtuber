FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖 (编译和基础音频库)
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libasound2-dev \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='redis', port=6379); r.ping()" || exit 1

# 启动应用
CMD ["python", "main.py"]