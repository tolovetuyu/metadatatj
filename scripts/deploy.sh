#!/bin/bash
# MetadataTJ 一键部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh

set -e

# ==================== 配置区域 ====================
# 请根据实际环境修改以下配置

# 阿里云镜像仓库
REGISTRY="crpi-zzqrsg0sczeik6kc.cn-hangzhou.personal.cr.aliyuncs.com"
NAMESPACE="metadatatj"
IMAGE_NAME="metadataj01"
IMAGE_TAG="latest"
FULL_IMAGE="${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

# 容器名称
CONTAINER_NAME="metadatatj"

# 服务端口（避免与其他服务冲突）
RECOMMEND_PORT=7058
TABLEMAP_PORT=7059
ADMIN_PORT=7060

# 数据存储目录
DATA_DIR="/opt/metadataTJ"

# 数据库配置（请修改为实际值）
DB_HOST="192.168.1.100"
DB_PORT="3306"
DB_USER="root"
DB_PASSWORD="your_password_here"
DB_NAME="metadata"

# 历史数据库配置（请修改为实际值）
HISTORY_DB_HOST="192.168.1.100"
HISTORY_DB_PORT="3306"
HISTORY_DB_USER="root"
HISTORY_DB_PASSWORD="your_password_here"
HISTORY_DB_NAME="metadata_history"

# LLM 配置（无大模型则禁用）
LLM_DECOMPOSE_ENABLED="false"
LLM_RERANK_ENABLED="false"

# ==================== 部署函数 ====================

echo "========================================"
echo "  MetadataTJ 一键部署脚本"
echo "========================================"

# 检查 Docker 是否安装
check_docker() {
    echo "[1/6] 检查 Docker 环境..."
    if ! command -v docker &> /dev/null; then
        echo "错误: Docker 未安装，请先安装 Docker"
        exit 1
    fi
    echo "Docker 版本: $(docker --version)"
}

# 创建目录
create_directories() {
    echo "[2/6] 创建数据目录..."
    mkdir -p "${DATA_DIR}/data"
    mkdir -p "${DATA_DIR}/logs"
    mkdir -p "${DATA_DIR}/knowledge"
    echo "目录创建完成: ${DATA_DIR}"
}

# 创建配置文件
create_config() {
    echo "[3/6] 创建环境配置文件..."
    cat > "${DATA_DIR}/.env" << EOF
# MetadataTJ 环境配置文件
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')

# 服务端口配置
RECOMMEND_HOST=0.0.0.0
RECOMMEND_PORT=${RECOMMEND_PORT}
TABLEMAP_HOST=0.0.0.0
TABLEMAP_PORT=${TABLEMAP_PORT}
ADMIN_HOST=0.0.0.0
ADMIN_PORT=${ADMIN_PORT}

# 数据源配置
DATA_SOURCE=db

# 主数据库配置
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=${DB_NAME}
DB_CHARSET=utf8mb4

# 历史数据库配置
HISTORY_DB_HOST=${HISTORY_DB_HOST}
HISTORY_DB_PORT=${HISTORY_DB_PORT}
HISTORY_DB_USER=${HISTORY_DB_USER}
HISTORY_DB_PASSWORD=${HISTORY_DB_PASSWORD}
HISTORY_DB_NAME=${HISTORY_DB_NAME}
HISTORY_DB_CHARSET=utf8mb4

# 历史推荐配置
HISTORY_RECOMMEND_ENABLED=true
HISTORY_RECOMMEND_TABLE=rucp_history_recommend_stat
HISTORY_SOURCE_TABLE=rucp_element_mapping_history
HISTORY_SYNC_INTERVAL_HOURS=24
TASK_PROCESS_TABLE=rucp_task_process

# LLM 配置（无大模型则禁用）
LLM_DECOMPOSE_ENABLED=${LLM_DECOMPOSE_ENABLED}
LLM_RERANK_ENABLED=${LLM_RERANK_ENABLED}

# Embedding 配置（离线模式无需配置）
EMBEDDING_API_BASE=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=

# 检索参数
RECALL_TOP_K=30
RERANK_TOP_K=5
TABLE_MATCH_THRESHOLD=0.75
FIELD_MATCH_THRESHOLD=0.80

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=/app/logs

# 向量库配置
CHROMA_PERSIST_DIR=/app/data/chroma
EOF
    echo "配置文件创建完成: ${DATA_DIR}/.env"
}

# 拉取镜像
pull_image() {
    echo "[4/6] 拉取 Docker 镜像..."
    echo "镜像地址: ${FULL_IMAGE}"
    
    # 检查是否需要登录
    echo "请输入阿里云镜像仓库用户名（如需要登录）:"
    read -r ALIYUN_USERNAME
    if [ -n "$ALIYUN_USERNAME" ]; then
        echo "请输入阿里云镜像仓库密码:"
        read -rs ALIYUN_PASSWORD
        docker login --username="${ALIYUN_USERNAME}" "${REGISTRY}" <<< "${ALIYUN_PASSWORD}"
        echo "登录成功"
    fi
    
    docker pull "${FULL_IMAGE}"
    echo "镜像拉取完成"
}

# 停止旧容器（如果存在）
stop_old_container() {
    echo "[5/6] 检查并停止旧容器..."
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "发现已存在的容器 ${CONTAINER_NAME}，正在停止..."
        docker stop "${CONTAINER_NAME}" 2>/dev/null || true
        docker rm "${CONTAINER_NAME}" 2>/dev/null || true
        echo "旧容器已移除"
    else
        echo "未发现已存在的容器"
    fi
}

# 启动容器
start_container() {
    echo "[6/6] 启动容器..."
    docker run -d \
        --name "${CONTAINER_NAME}" \
        --restart unless-stopped \
        -p "${RECOMMEND_PORT}:${RECOMMEND_PORT}" \
        -p "${TABLEMAP_PORT}:${TABLEMAP_PORT}" \
        -p "${ADMIN_PORT}:${ADMIN_PORT}" \
        -v "${DATA_DIR}/data:/app/data" \
        -v "${DATA_DIR}/logs:/app/logs" \
        -v "${DATA_DIR}/knowledge:/app/knowledge" \
        --env-file "${DATA_DIR}/.env" \
        --cap-add=SYS_NICE \
        --security-opt seccomp=unconfined \
        "${FULL_IMAGE}"
    
    echo "容器启动完成"
}

# 等待服务启动
wait_for_service() {
    echo ""
    echo "等待服务启动..."
    sleep 10
    
    # 检查容器状态
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "容器运行正常"
    else
        echo "警告: 容器可能未正常启动，请检查日志"
        docker logs "${CONTAINER_NAME}"
        exit 1
    fi
}

# 显示部署结果
show_result() {
    echo ""
    echo "========================================"
    echo "  部署完成"
    echo "========================================"
    echo ""
    echo "容器名称: ${CONTAINER_NAME}"
    echo "镜像版本: ${FULL_IMAGE}"
    echo ""
    echo "服务地址:"
    echo "  - 推荐服务: http://localhost:${RECOMMEND_PORT}"
    echo "  - 表映射服务: http://localhost:${TABLEMAP_PORT}"
    echo "  - 管理后台: http://localhost:${ADMIN_PORT}"
    echo ""
    echo "数据目录: ${DATA_DIR}"
    echo "配置文件: ${DATA_DIR}/.env"
    echo ""
    echo "常用命令:"
    echo "  查看日志:   docker logs -f ${CONTAINER_NAME}"
    echo "  重启容器:   docker restart ${CONTAINER_NAME}"
    echo "  停止容器:   docker stop ${CONTAINER_NAME}"
    echo "  进入容器:   docker exec -it ${CONTAINER_NAME} bash"
    echo ""
    echo "首次使用请执行数据同步:"
    echo "  curl -X POST http://localhost:${RECOMMEND_PORT}/autoexport/api/history/sync -H 'Content-Type: application/json' -d '{\"force_full\": true, \"source\": \"task_process\"}'"
    echo ""
}

# ==================== 主流程 ====================

check_docker
create_directories
create_config
pull_image
stop_old_container
start_container
wait_for_service
show_result