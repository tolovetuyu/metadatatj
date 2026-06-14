# MetadataTJ 推荐服务 Dockerfile
# 多阶段构建，优化镜像大小

# ==================== 构建阶段 ====================
# 使用阿里云镜像加速构建
FROM registry.cn-hangzhou.aliyuncs.com/acs-sample/python:3.11-slim AS builder

WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖到虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 配置 pip 国内镜像源并安装依赖
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==================== 运行阶段 ====================
# 使用阿里云镜像加速构建
FROM registry.cn-hangzhou.aliyuncs.com/acs-sample/python:3.11-slim AS runtime

LABEL maintainer="metadataTJ"
LABEL description="MetadataTJ 数据元推荐服务"
LABEL version="1.0.0"

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data/chroma /app/logs /app/knowledge

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY .env.example ./.env.example

# 复制启动脚本
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# 环境变量默认值
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # 服务端口
    RECOMMEND_PORT=6058 \
    TABLEMAP_PORT=6059 \
    ADMIN_PORT=6060 \
    # 数据源模式（推荐数据库模式）
    DATA_SOURCE=db \
    # 数据库配置
    DB_HOST=host.docker.internal \
    DB_PORT=3306 \
    DB_USER=root \
    DB_NAME=metadata \
    # 向量库路径
    CHROMA_PERSIST_DIR=/app/data/chroma \
    # 知识库路径
    KNOWLEDGE_DIR=/app/knowledge \
    # 日志路径
    LOG_DIR=/app/logs

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${RECOMMEND_PORT}/autoexport/api/recommend -X POST -H "Content-Type: application/json" -d '{"fieldsInfo":[]}' || exit 1

# 暴露端口
EXPOSE 6058 6059 6060

# 数据卷
VOLUME ["/app/data", "/app/logs", "/app/knowledge"]

# 启动入口
ENTRYPOINT ["/entrypoint.sh"]

# 默认启动所有服务
CMD ["all"]
