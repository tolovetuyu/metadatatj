#!/bin/bash
# MetadataTJ 快速部署脚本（交互式配置）
# 使用方法: chmod +x deploy-interactive.sh && ./deploy-interactive.sh

set -e

echo "========================================"
echo "  MetadataTJ 快速部署脚本"
echo "========================================"
echo ""

# ==================== 交互式配置 ====================

echo "请输入部署配置（直接回车使用默认值）:"
echo ""

# 数据存储目录
read -rp "数据存储目录 [默认: /opt/metadataTJ]: " DATA_DIR
DATA_DIR=${DATA_DIR:-/opt/metadataTJ}

# 服务端口
read -rp "推荐服务端口 [默认: 7058]: " RECOMMEND_PORT
RECOMMEND_PORT=${RECOMMEND_PORT:-7058}

read -rp "表映射服务端口 [默认: 7059]: " TABLEMAP_PORT
TABLEMAP_PORT=${TABLEMAP_PORT:-7059}

read -rp "管理后台端口 [默认: 7060]: " ADMIN_PORT
ADMIN_PORT=${ADMIN_PORT:-7060}

# 数据库配置
echo ""
echo "=== 主数据库配置 ==="
read -rp "数据库地址 [默认: 192.168.1.100]: " DB_HOST
DB_HOST=${DB_HOST:-192.168.1.100}

read -rp "数据库端口 [默认: 3306]: " DB_PORT
DB_PORT=${DB_PORT:-3306}

read -rp "数据库用户名 [默认: root]: " DB_USER
DB_USER=${DB_USER:-root}

read -rp "数据库密码: " DB_PASSWORD
if [ -z "$DB_PASSWORD" ]; then
    echo "错误: 数据库密码不能为空"
    exit 1
fi

read -rp "数据库库名 [默认: metadata]: " DB_NAME
DB_NAME=${DB_NAME:-metadata}

# 历史数据库配置
echo ""
echo "=== 历史数据库配置 ==="
read -rp "历史数据库地址 [默认: 同主库]: " HISTORY_DB_HOST
HISTORY_DB_HOST=${HISTORY_DB_HOST:-$DB_HOST}

read -rp "历史数据库端口 [默认: 同主库]: " HISTORY_DB_PORT
HISTORY_DB_PORT=${HISTORY_DB_PORT:-$DB_PORT}

read -rp "历史数据库用户名 [默认: 同主库]: " HISTORY_DB_USER
HISTORY_DB_USER=${HISTORY_DB_USER:-$DB_USER}

read -rp "历史数据库密码 [默认: 同主库]: " HISTORY_DB_PASSWORD
HISTORY_DB_PASSWORD=${HISTORY_DB_PASSWORD:-$DB_PASSWORD}

read -rp "历史数据库库名 [默认: metadata_history]: " HISTORY_DB_NAME
HISTORY_DB_NAME=${HISTORY_DB_NAME:-metadata_history}

# LLM 配置
echo ""
echo "=== LLM 配置 ==="
read -rp "是否启用 LLM 分解 [默认: false]: " LLM_DECOMPOSE_ENABLED
LLM_DECOMPOSE_ENABLED=${LLM_DECOMPOSE_ENABLED:-false}

read -rp "是否启用 LLM 精排 [默认: false]: " LLM_RERANK_ENABLED
LLM_RERANK_ENABLED=${LLM_RERANK_ENABLED:-false}

# 镜像配置
REGISTRY="crpi-zzqrsg0sczeik6kc.cn-hangzhou.personal.cr.aliyuncs.com"
NAMESPACE="metadatatj"
IMAGE_NAME="metadataj01"
IMAGE_TAG="latest"
FULL_IMAGE="${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

CONTAINER_NAME="metadatatj"

echo ""
echo "========================================"
echo "  配置确认"
echo "========================================"
echo ""
echo "数据目录: ${DATA_DIR}"
echo "推荐服务端口: ${RECOMMEND_PORT}"
echo "表映射服务端口: ${TABLEMAP_PORT}"
echo "管理后台端口: ${ADMIN_PORT}"
echo "主数据库: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "历史数据库: ${HISTORY_DB_HOST}:${HISTORY_DB_PORT}/${HISTORY_DB_NAME}"
echo "LLM 分解: ${LLM_DECOMPOSE_ENABLED}"
echo "LLM 精排: ${LLM_RERANK_ENABLED}"
echo "镜像: ${FULL_IMAGE}"
echo ""

read -rp "确认以上配置，继续部署? [y/N]: " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "部署已取消"
    exit 0
fi

# ==================== 执行部署 ====================

echo ""
echo "[1/6] 创建数据目录..."
mkdir -p "${DATA_DIR}/data"
mkdir -p "${DATA_DIR}/logs"
mkdir -p "${DATA_DIR}/knowledge"

echo "[2/6] 创建配置文件..."
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

# LLM 配置
LLM_DECOMPOSE_ENABLED=${LLM_DECOMPOSE_ENABLED}
LLM_RERANK_ENABLED=${LLM_RERANK_ENABLED}

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

echo "[3/6] 拉取镜像..."
docker pull "${FULL_IMAGE}" || {
    echo "镜像拉取失败，尝试登录阿里云镜像仓库..."
    read -rp "请输入阿里云用户名: " ALIYUN_USER
    read -rp "请输入阿里云密码: " ALIYUN_PASS
    docker login --username="${ALIYUN_USER}" "${REGISTRY}" <<< "${ALIYUN_PASS}"
    docker pull "${FULL_IMAGE}"
}

echo "[4/6] 停止旧容器..."
docker stop "${CONTAINER_NAME}" 2>/dev/null || true
docker rm "${CONTAINER_NAME}" 2>/dev/null || true

echo "[5/6] 启动容器..."
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

echo "[6/6] 等待服务启动..."
sleep 10

# ==================== 显示结果 ====================

echo ""
echo "========================================"
echo "  部署完成"
echo "========================================"
echo ""
echo "容器名称: ${CONTAINER_NAME}"
echo ""
echo "服务地址:"
echo "  - 推荐服务: http://localhost:${RECOMMEND_PORT}"
echo "  - 表映射服务: http://localhost:${TABLEMAP_PORT}"
echo "  - 管理后台: http://localhost:${ADMIN_PORT}"
echo ""
echo "常用命令:"
echo "  查看日志: docker logs -f ${CONTAINER_NAME}"
echo "  重启容器: docker restart ${CONTAINER_NAME}"
echo "  进入容器: docker exec -it ${CONTAINER_NAME} bash"
echo ""
echo "首次使用请执行数据同步:"
echo "  curl -X POST http://localhost:${RECOMMEND_PORT}/autoexport/api/history/sync -H 'Content-Type: application/json' -d '{\"force_full\": true, \"source\": \"task_process\"}'"
echo ""