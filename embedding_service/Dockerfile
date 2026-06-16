# 本地向量模型服务 Dockerfile
# 使用 FastEmbed 提供中文向量计算服务

FROM python:3.11-slim

LABEL maintainer="metadataTJ Embedding Service"
LABEL description="Local Chinese text embedding service with FastEmbed"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务代码
COPY server.py .

# 预下载模型（可选，首次启动会自动下载）
# RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-base-zh-v1.5')"

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动服务
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]