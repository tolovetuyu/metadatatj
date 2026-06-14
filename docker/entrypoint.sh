#!/bin/bash
# MetadataTJ Docker 入口脚本
# 支持启动单个服务或全部服务

set -e

# 服务端口配置
RECOMMEND_PORT=${RECOMMEND_PORT:-6058}
TABLEMAP_PORT=${TABLEMAP_PORT:-6059}
ADMIN_PORT=${ADMIN_PORT:-6060}

# 切换到应用目录
cd /app

# 创建必要目录
mkdir -p /app/data/chroma /app/logs /app/knowledge

# 复制默认环境配置
if [ ! -f /app/.env ]; then
    cp /app/.env.example /app/.env
fi

# 构建向量索引（如果不存在）
build_index() {
    echo "检查向量索引..."
    if [ ! -f "/app/data/chroma/chroma.sqlite3" ] || [ "$(ls -A /app/data/chroma 2>/dev/null)" = "" ]; then
        echo "向量索引不存在，开始构建..."
        python scripts/build_index.py
        echo "向量索引构建完成"
    else
        echo "向量索引已存在"
    fi
}

# 启动推荐服务
start_recommend() {
    echo "启动推荐服务 (端口: ${RECOMMEND_PORT})..."
    export RECOMMEND_PORT
    exec python src/tornado_server_recommend.py
}

# 启动表映射服务
start_tablemap() {
    echo "启动表映射服务 (端口: ${TABLEMAP_PORT})..."
    export TABLEMAP_PORT
    exec python src/tornado_server_tablemap.py
}

# 启动管理后台
start_admin() {
    echo "启动管理后台 (端口: ${ADMIN_PORT})..."
    export ADMIN_PORT
    exec python src/tornado_server_admin.py
}

# 启动所有服务
start_all() {
    echo "启动所有服务..."
    echo "  - 推荐服务: 端口 ${RECOMMEND_PORT}"
    echo "  - 表映射服务: 端口 ${TABLEMAP_PORT}"
    echo "  - 管理后台: 端口 ${ADMIN_PORT}"
    
    # 后台启动各服务
    export RECOMMEND_PORT TABLEMAP_PORT ADMIN_PORT
    
    python src/tornado_server_recommend.py &
    RECOMMEND_PID=$!
    
    python src/tornado_server_tablemap.py &
    TABLEMAP_PID=$!
    
    python src/tornado_server_admin.py &
    ADMIN_PID=$!
    
    echo "服务已启动:"
    echo "  - 推荐服务 PID: ${RECOMMEND_PID}"
    echo "  - 表映射服务 PID: ${TABLEMAP_PID}"
    echo "  - 管理后台 PID: ${ADMIN_PID}"
    
    # 等待任意进程退出
    wait -n $RECOMMEND_PID $TABLEMAP_PID $ADMIN_PID
    
    # 如果有进程退出，终止所有进程
    echo "检测到服务退出，正在停止所有服务..."
    kill $RECOMMEND_PID $TABLEMAP_PID $ADMIN_PID 2>/dev/null || true
    exit 1
}

# 显示帮助
show_help() {
    echo "MetadataTJ 数据元推荐服务"
    echo ""
    echo "用法: docker run metadatatj [命令]"
    echo ""
    echo "命令:"
    echo "  recommend    启动推荐服务 (端口 ${RECOMMEND_PORT})"
    echo "  tablemap     启动表映射服务 (端口 ${TABLEMAP_PORT})"
    echo "  admin        启动管理后台 (端口 ${ADMIN_PORT})"
    echo "  all          启动所有服务"
    echo "  build-index  仅构建向量索引"
    echo "  help         显示此帮助信息"
    echo ""
    echo "环境变量:"
    echo "  DATA_SOURCE              数据源模式 (file/db)"
    echo "  LLM_API_KEY              LLM API密钥"
    echo "  LLM_BASE_URL             LLM API地址"
    echo "  HISTORY_RECOMMEND_ENABLED 启用历史推荐"
    echo "  DB_HOST                  数据库地址"
    echo "  DB_PORT                  数据库端口"
    echo "  DB_USER                  数据库用户"
    echo "  DB_PASSWORD              数据库密码"
    echo "  DB_NAME                  数据库名称"
}

# 主入口
case "${1:-all}" in
    recommend)
        build_index
        start_recommend
        ;;
    tablemap)
        build_index
        start_tablemap
        ;;
    admin)
        start_admin
        ;;
    all)
        build_index
        start_all
        ;;
    build-index)
        build_index
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "错误: 未知命令 '${1}'"
        show_help
        exit 1
        ;;
esac
