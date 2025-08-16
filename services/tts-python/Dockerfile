FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（TTS可能需要额外的音频库）
RUN apt-get update && apt-get install -y \
    gcc \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 复制并设置entrypoint脚本权限
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 创建非root用户和共享目录
RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /tmp/aivtuber_tasks \
    && chown -R app:app /app /tmp/aivtuber_tasks \
    && apt-get update && apt-get install -y sudo \
    && echo "app ALL=(ALL) NOPASSWD: /bin/chown, /bin/chmod" >> /etc/sudoers \
    && rm -rf /var/lib/apt/lists/*
USER app

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='redis', port=6379); r.ping()" || exit 1

# 使用entrypoint脚本
ENTRYPOINT ["/entrypoint.sh"]