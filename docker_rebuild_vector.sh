#!/bin/bash
# Docker 环境下重建向量索引脚本
# 使用方式：bash docker_rebuild_vector.sh <容器名>

# 设置容器名（如果没有参数，使用默认值）
CONTAINER_NAME=${1:-"metadataTJ"}

echo "=========================================="
echo "向量索引重建脚本"
echo "容器名: $CONTAINER_NAME"
echo "=========================================="

echo ""
echo "步骤1: 复制最新代码到容器..."
docker cp src/services/recommender.py $CONTAINER_NAME:/app/src/services/recommender.py
docker cp src/knowledge_loader.py $CONTAINER_NAME:/app/src/services/knowledge_loader.py
docker cp scripts/build_index.py $CONTAINER_NAME:/app/scripts/build_index.py

echo ""
echo "步骤2: 进入容器执行重建脚本..."
docker exec -it $CONTAINER_NAME bash -c "
cd /app && \
echo '开始重建向量索引...' && \
python scripts/build_index.py && \
echo '重建完成！'
"

echo ""
echo "步骤3: 重启容器让修改生效..."
docker restart $CONTAINER_NAME

echo ""
echo "步骤4: 等待服务启动（10秒）..."
sleep 10

echo ""
echo "步骤5: 验证修复结果..."
docker exec -it $CONTAINER_NAME python -c "
import sys
sys.path.insert(0, '/app/src')
from vector.chroma_store import ChromaVectorStore
store = ChromaVectorStore()
print('==========================================')
print('验证向量库是否有 code 字段')
print('==========================================')
for code in ['DE00000002', 'DE00000003', 'DE00000609']:
    meta = store.get_element_by_code(code)
    if meta:
        print(f'✓ {code}: code={meta.get(\"code\")}')
        if meta.get('code'):
            print(f'  ✅ code 字段存在！')
        else:
            print(f'  ❌ code 字段仍然为空')
    else:
        print(f'❌ {code}: 未找到')
print('==========================================')
"

echo ""
echo "=========================================="
echo "重建完成！"
echo "现在调用推荐接口，ename 应该返回数据元标识符（如 XM）"
echo "=========================================="