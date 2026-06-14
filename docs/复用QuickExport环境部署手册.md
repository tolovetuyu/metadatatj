# 复用 QuickExport Docker 环境部署 MetadataTJ 操作手册

## 一、环境说明

### 1.1 现有环境

```
内网服务器
├── Docker 已安装并运行
├── QuickExport 容器正在运行
│   ├── 端口: 8080 (或其他端口)
│   ├── 数据库: MySQL (192.168.x.x)
│   └── 知识库文件: /opt/quick/knowledge/
└── 需要部署: MetadataTJ
```

### 1.2 目标架构

```
内网服务器
├── QuickExport (端口 8080 或 6058) - 保持运行
└── MetadataTJ (端口 6058/6059/6060 或 7058/7059/7060) - 新增部署
```

**重要：如果 QuickExport 使用 6058/6059/6060 端口，需要修改 MetadataTJ 端口避免冲突。**

---

## 二、准备工作

### 2.1 检查现有环境

```bash
# SSH 登录内网服务器
ssh user@192.168.x.x

# 检查 Docker 状态
docker info

# 查看现有容器
docker ps

# 输出示例
CONTAINER ID   IMAGE              STATUS          PORTS
abc123         quickexport:latest Up 2 days       0.0.0.0:8080->8080/tcp
# 或
abc123         quickexport:latest Up 2 days       0.0.0.0:6058-6060->6058-6060/tcp
```

### 2.2 端口冲突处理

**检查 QuickExport 使用的端口：**

```bash
# 查看 QuickExport 容器端口映射
docker port quickexport

# 输出示例
6058/tcp -> 0.0.0.0:6058
6059/tcp -> 0.0.0.0:6059
6060/tcp -> 0.0.0.0:6060
```

**如果端口冲突，选择以下方案：**

#### 方案一：修改 MetadataTJ 端口（推荐）

```bash
# MetadataTJ 使用新端口
RECOMMEND_PORT=7058
TABLEMAP_PORT=7059
ADMIN_PORT=7060

# 启动命令
docker run -d \
    -p 7058:7058 \
    -p 7059:7059 \
    -p 7060:7060 \
    ...
```

#### 方案二：停止 QuickExport

```bash
# 停止并备份 QuickExport
docker stop quickexport
docker rename quickexport quickexport-backup

# MetadataTJ 使用原端口
docker run -d \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    ...
```

**端口规划：**

| 场景 | QuickExport | MetadataTJ |
|------|------------|------------|
| 无冲突 | 8080 | 6058/6059/6060 |
| 有冲突（共存） | 6058/6059/6060 | **7058/7059/7060** |
| 替换 | 停止 | 6058/6059/6060 |

### 2.3 获取项目代码

**重要：代码是通过 Dockerfile 自动复制到镜像中的，不需要手动传入 Docker。**

```
构建流程：
docker build → Dockerfile COPY src/ ./src/ → 代码自动打包进镜像
```

**方式一：从开发机上传**

```bash
# 在开发机上执行
scp -r d:\workspace\metadataTJ user@192.168.x.x:/opt/metadatatj
```

**方式二：从内网 Git 仓库克隆**

```bash
# 在内网服务器上执行
cd /opt
git clone http://git.internal.com/metadatatj.git
```

**方式三：U盘拷贝**

```bash
# 将项目打包
cd d:\workspace\metadataTJ
tar -czvf metadatatj.tar.gz .

# 复制到U盘，然后在服务器上解压
tar -xzvf metadatatj.tar.gz -C /opt/metadatatj
```

---

## 三、构建镜像

### 3.1 方式一：直接构建（推荐）

```bash
cd /opt/metadatatj/docker

# 构建镜像
docker build -t metadatatj:latest .

# 查看镜像
docker images metadatatj
```

**构建时间约 5-10 分钟**

### 3.2 方式二：导入预构建镜像

如果已在外部构建好镜像：

```bash
# 导入镜像
docker load -i metadatatj.tar

# 验证
docker images metadatatj
```

---

## 四、配置环境变量

### 4.1 创建配置文件

```bash
cd /opt/metadatatj
cp .env.example .env
vim .env
```

### 4.2 配置内容

```bash
# ========== 服务端口 ==========
RECOMMEND_PORT=6058
TABLEMAP_PORT=6059
ADMIN_PORT=6060

# ========== 数据源配置 ==========
DATA_SOURCE=db

# 主数据库（复用 QuickExport 的数据库）
DB_HOST=192.168.x.x
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=metadata

# 历史数据库（如果与主库相同，填写相同配置）
HISTORY_DB_HOST=192.168.x.x
HISTORY_DB_PORT=3306
HISTORY_DB_USER=root
HISTORY_DB_PASSWORD=your_password
HISTORY_DB_NAME=metadata_history

# ========== LLM 配置 ==========
# 如果内网有大模型服务
LLM_API_BASE=http://192.168.x.x:8000/v1
LLM_API_KEY=internal-key
LLM_MODEL=qwen-plus

# 如果无大模型服务，禁用 LLM 功能
LLM_DECOMPOSE_ENABLED=false
LLM_RERANK_ENABLED=false

# ========== Embedding 配置 ==========
# 如果内网有向量服务
EMBEDDING_API_BASE=http://192.168.x.x:8000/v1
EMBEDDING_API_KEY=internal-key
EMBEDDING_MODEL=text-embedding-v3

# ========== 推荐配置 ==========
RECALL_TOP_K=30
RERANK_TOP_K=5

# ========== 历史推荐配置 ==========
HISTORY_RECOMMEND_ENABLED=true
HISTORY_SYNC_INTERVAL_HOURS=24
```

### 4.3 获取 QuickExport 数据库配置

```bash
# 查看 QuickExport 容器的环境变量
docker inspect quickexport | grep -A 20 "Env"

# 或查看 QuickExport 的配置文件
cat /opt/quick/.env
```

---

## 五、启动服务

### 5.1 创建数据目录

```bash
mkdir -p /opt/metadatatj/{data,logs}
```

### 5.2 启动容器

```bash
docker run -d \
    --name metadatatj \
    --restart unless-stopped \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    -v /opt/metadatatj/data:/app/data \
    -v /opt/metadatatj/logs:/app/logs \
    --env-file /opt/metadatatj/.env \
    metadatatj:latest all
```

### 5.3 查看启动日志

```bash
# 实时查看日志
docker logs -f metadatatj

# 正常启动日志示例
检查向量索引...
向量索引不存在，开始构建...
加载知识库...
  - 数据元: 2000 条
  - 限定词: 500 条
构建向量索引...
向量索引构建完成
启动所有服务...
  - 推荐服务: 端口 6058
  - 表映射服务: 端口 6059
  - 管理后台: 端口 6060
服务已启动
```

---

## 六、验证服务

### 6.1 检查容器状态

```bash
docker ps

# 输出示例
CONTAINER ID   IMAGE              STATUS          PORTS
abc123         quickexport:latest Up 2 days       0.0.0.0:8080->8080/tcp
def456         metadatatj:latest  Up 1 minute     0.0.0.0:6058-6060->6058-6060/tcp
```

### 6.2 测试推荐接口

```bash
# 测试推荐服务
curl -X POST http://localhost:6058/autoexport/api/recommend \
    -H "Content-Type: application/json" \
    -d '{
        "fieldsInfo": [
            {
                "cname": "姓名",
                "ename": "XM"
            }
        ]
    }'

# 预期返回
{
    "recommendInfos": [
        {
            "element": {
                "cname": ["姓名", "人员姓名", ...],
                "ename": ["XM", "RYXM", ...],
                ...
            }
        }
    ]
}
```

### 6.3 测试管理后台

```bash
# 访问管理后台
curl http://localhost:6060/

# 或在浏览器打开
# http://192.168.x.x:6060
```

---

## 七、配置 Nginx 反向代理（可选）

### 7.1 安装 Nginx

```bash
# CentOS
yum install -y nginx

# Ubuntu
apt-get install -y nginx
```

### 7.2 配置反向代理

```bash
cat > /etc/nginx/conf.d/api.conf << 'EOF'
upstream quickexport {
    server 127.0.0.1:8080;
}

upstream metadatatj {
    server 127.0.0.1:6058;
}

server {
    listen 80;
    server_name _;

    # QuickExport (旧接口)
    location /quickexport/ {
        proxy_pass http://quickexport/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # MetadataTJ (新接口)
    location /metadatatj/ {
        proxy_pass http://metadatatj/autoexport/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 兼容旧接口路径（可选）
    location /autoexport/api/ {
        proxy_pass http://metadatatj/autoexport/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# 测试配置
nginx -t

# 重载配置
nginx -s reload
```

### 7.3 测试反向代理

```bash
# 通过 Nginx 访问
curl -X POST http://192.168.x.x/metadatatj/recommend \
    -H "Content-Type: application/json" \
    -d '{"fieldsInfo": [{"cname": "姓名", "ename": "XM"}]}'
```

---

## 八、日常运维

### 8.1 查看日志

```bash
# 实时查看日志
docker logs -f metadatatj

# 查看最近 100 行
docker logs --tail 100 metadatatj

# 查看日志文件
tail -f /opt/metadatatj/logs/recommend.log
```

### 8.2 重启服务

```bash
# 重启容器
docker restart metadatatj

# 优雅停止
docker stop -t 30 metadatatj
docker start metadatatj
```

### 8.3 更新服务

```bash
# 1. 停止旧容器
docker stop metadatatj
docker rename metadatatj metadatatj-backup

# 2. 构建新镜像
cd /opt/metadatatj
git pull
cd docker
docker build -t metadatatj:latest .

# 3. 启动新容器
docker run -d \
    --name metadatatj \
    --restart unless-stopped \
    -p 6058:6058 -p 6059:6059 -p 6060:6060 \
    -v /opt/metadatatj/data:/app/data \
    -v /opt/metadatatj/logs:/app/logs \
    --env-file /opt/metadatatj/.env \
    metadatatj:latest all

# 4. 验证成功后删除旧容器
docker rm metadatatj-backup
```

### 8.4 备份数据

```bash
# 备份向量库
tar -czvf chroma_backup_$(date +%Y%m%d).tar.gz /opt/metadatatj/data/chroma

# 备份配置
cp /opt/metadatatj/.env /backup/metadatatj.env.$(date +%Y%m%d)
```

---

## 九、故障排查

### 9.1 容器无法启动

```bash
# 查看详细日志
docker logs metadatatj

# 常见错误及解决
```

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `数据库连接失败` | DB 配置错误 | 检查 .env 中的 DB_HOST/DB_PASSWORD |
| `端口已被占用` | 端口冲突 | 修改端口配置或停止冲突服务 |
| `向量索引构建失败` | 内存不足 | 增加容器内存限制 |
| `知识库加载失败` | 数据库无数据 | 检查数据库表是否有数据 |

### 9.2 推荐返回空结果

```bash
# 检查向量库
ls -la /opt/metadatatj/data/chroma/

# 检查知识库数据
docker exec metadatatj python -c "
from knowledge_loader import load_knowledge
kb = load_knowledge()
print(f'数据元: {len(kb.element_items)}')
print(f'限定词: {len(kb.determine_items)}')
"

# 重建向量索引
docker exec metadatatj python scripts/build_index.py
```

### 9.3 性能问题

```bash
# 查看资源使用
docker stats metadatatj

# 增加资源限制
docker update --memory 8g --cpus 4 metadatatj
```

---

## 十、完整操作清单

### 部署前检查

- [ ] Docker 正常运行
- [ ] 端口 6058/6059/6060 未被占用
- [ ] 磁盘空间 > 5GB
- [ ] 项目代码已上传
- [ ] 数据库连接信息已确认

### 部署步骤

- [ ] 1. 上传项目代码到 /opt/metadatatj
- [ ] 2. 构建 Docker 镜像
- [ ] 3. 配置 .env 文件
- [ ] 4. 创建数据目录
- [ ] 5. 启动容器
- [ ] 6. 查看启动日志
- [ ] 7. 测试推荐接口
- [ ] 8. 配置 Nginx（可选）

### 部署后验证

- [ ] 容器状态为 Up
- [ ] 推荐接口返回正常
- [ ] 管理后台可访问
- [ ] QuickExport 服务正常（未受影响）

---

## 十一、快速部署脚本

```bash
#!/bin/bash
# quick_deploy.sh - 快速部署脚本

set -e

PROJECT_DIR="${1:-/opt/metadatatj}"
DB_HOST="${2:-192.168.1.100}"
DB_PASSWORD="${3:-password}"

echo "========== MetadataTJ 快速部署 =========="
echo "项目目录: $PROJECT_DIR"
echo "数据库: $DB_HOST"

# 1. 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

# 2. 检查端口
for port in 6058 6059 6060; do
    if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        echo "错误: 端口 $port 已被占用"
        exit 1
    fi
done

# 3. 构建镜像
echo "[1/5] 构建镜像..."
cd "$PROJECT_DIR/docker"
docker build -t metadatatj:latest .

# 4. 配置环境变量
echo "[2/5] 配置环境变量..."
cd "$PROJECT_DIR"
if [ ! -f .env ]; then
    cat > .env << EOF
DATA_SOURCE=db
DB_HOST=$DB_HOST
DB_PORT=3306
DB_USER=root
DB_PASSWORD=$DB_PASSWORD
DB_NAME=metadata
HISTORY_DB_HOST=$DB_HOST
HISTORY_DB_PORT=3306
HISTORY_DB_USER=root
HISTORY_DB_PASSWORD=$DB_PASSWORD
HISTORY_DB_NAME=metadata_history
LLM_DECOMPOSE_ENABLED=false
LLM_RERANK_ENABLED=false
RECALL_TOP_K=30
RERANK_TOP_K=5
HISTORY_RECOMMEND_ENABLED=true
EOF
fi

# 5. 创建目录
echo "[3/5] 创建数据目录..."
mkdir -p "$PROJECT_DIR"/{data,logs}

# 6. 启动容器
echo "[4/5] 启动容器..."
docker stop metadatatj 2>/dev/null || true
docker rm metadatatj 2>/dev/null || true

docker run -d \
    --name metadatatj \
    --restart unless-stopped \
    -p 6058:6058 -p 6059:6059 -p 6060:6060 \
    -v "$PROJECT_DIR/data:/app/data" \
    -v "$PROJECT_DIR/logs:/app/logs" \
    --env-file "$PROJECT_DIR/.env" \
    metadatatj:latest all

# 7. 等待启动
echo "[5/5] 等待服务启动..."
sleep 10

# 8. 验证
echo ""
echo "验证服务..."
if docker ps | grep -q metaditatj; then
    echo "✅ 部署成功！"
    echo ""
    echo "服务地址:"
    echo "  - 推荐服务: http://$(hostname -I | awk '{print $1}'):6058"
    echo "  - 表映射服务: http://$(hostname -I | awk '{print $1}'):6059"
    echo "  - 管理后台: http://$(hostname -I | awk '{print $1}'):6060"
else
    echo "❌ 部署失败"
    docker logs metadatatj
fi
```

**使用方法**:
```bash
chmod +x quick_deploy.sh
./quick_deploy.sh /opt/metadatatj 192.168.1.100 your_password
```

---

## 十二、与 QuickExport 对比

| 项目 | QuickExport | MetadataTJ |
|------|------------|------------|
| 端口 | 8080 | 6058/6059/6060 |
| 数据源 | Excel | 数据库 |
| 向量库 | SimCSE | ChromaDB |
| 历史推荐 | ❌ | ✅ |
| LLM精排 | ❌ | ✅ |
| 管理后台 | ❌ | ✅ |

**两个服务可以同时运行，互不影响。**
