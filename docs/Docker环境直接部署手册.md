# Docker 环境直接部署 MetadataTJ 操作手册

## 一、环境说明

### 1.1 前提条件

```
内网服务器
├── Docker 已安装并运行
├── 未安装 QuickExport（或不需要共存）
└── 需要部署: MetadataTJ
```

### 1.2 目标架构

```
内网服务器
└── MetadataTJ
    ├── 推荐服务 (端口 6058)
    ├── 表映射服务 (端口 6059)
    └── 管理后台 (端口 6060)
```

---

## 二、部署前检查

### 2.1 检查 Docker 环境

```bash
# SSH 登录内网服务器
ssh user@192.168.x.x

# 检查 Docker 版本
docker --version
# 要求: Docker version 20.10+

# 检查 Docker 服务状态
systemctl status docker
# 或
service docker status

# 如果 Docker 未启动，启动它
systemctl start docker
systemctl enable docker
```

### 2.2 检查系统资源

```bash
# 检查磁盘空间
df -h
# 要求: 至少 10GB 可用空间

# 检查内存
free -h
# 要求: 至少 4GB 内存

# 检查 CPU
nproc
# 建议: 2核以上
```

### 2.3 检查端口

```bash
# 检查端口是否被占用
netstat -tlnp | grep -E '6058|6059|6060'
# 或
ss -tlnp | grep -E '6058|6059|6060'
```

#### 端口冲突处理

**如果端口已被占用（如 QuickExport 使用相同端口），有以下解决方案：**

**方案一：修改 MetadataTJ 端口（推荐，不影响现有服务）**

```bash
# 修改 .env 文件中的端口配置
RECOMMEND_PORT=7058    # 改为未占用的端口
TABLEMAP_PORT=7059
ADMIN_PORT=7060

# 启动时使用新端口
docker run -d \
    -p 7058:7058 \
    -p 7059:7059 \
    -p 7060:7060 \
    ...
```

**方案二：停止占用端口的容器**

```bash
# 查看占用端口的容器
docker ps | grep 6058

# 停止容器
docker stop quickexport

# 可选：重命名备份
docker rename quickexport quickexport-backup
```

**方案三：使用不同端口共存**

```bash
# QuickExport: 6058/6059/6060 (保持不变)
# MetadataTJ:  7058/7059/7060 (新端口)

# 通过 Nginx 反向代理统一入口
# /quickexport/* -> QuickExport:6058
# /metadatatj/*  -> MetadataTJ:7058
```

**端口规划建议：**

| 服务 | 默认端口 | 冲突时建议端口 |
|------|---------|---------------|
| QuickExport 推荐 | 6058 | 6058 (保持) |
| QuickExport 表映射 | 6059 | 6059 (保持) |
| MetadataTJ 推荐 | 6058 | **7058** |
| MetadataTJ 表映射 | 6059 | **7059** |
| MetadataTJ 管理后台 | 6060 | **7060** |

### 2.4 检查数据库连接

```bash
# 测试数据库连通性
telnet 192.168.x.x 3306
# 或
nc -zv 192.168.x.x 3306

# 如果有 mysql 客户端
mysql -h 192.168.x.x -u root -p -e "SELECT 1"
```

---

## 三、获取项目代码

### 3.0 Docker 构建原理说明

**重要：代码是通过 Dockerfile 自动复制到镜像中的，不需要手动传入 Docker。**

```
构建流程：
┌─────────────────────────────────────────────────────────────┐
│  docker build -t metadatatj:latest .                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Dockerfile 执行：                                          │
│  1. FROM python:3.11-slim      # 拉取基础镜像               │
│  2. COPY requirements.txt .    # 复制依赖文件               │
│  3. RUN pip install ...        # 安装依赖                   │
│  4. COPY src/ ./src/           # ✅ 自动复制代码到镜像      │
│  5. COPY knowledge/ ./knowledge/ # 复制知识库               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  生成最终镜像 (metadatatj:latest)                           │
│  包含：Python + 依赖 + 代码 + 知识库                        │
└─────────────────────────────────────────────────────────────┘
```

**所以只需要：**
1. 将代码上传到服务器（如 `/opt/metadatatj`）
2. 执行 `docker build` 命令
3. Docker 会自动将代码打包进镜像

### 3.1 方式一：从开发机上传（推荐）

```bash
# === 在开发机（Windows）上执行 ===

# 方式 A: 使用 scp
scp -r d:\workspace\metadataTJ user@192.168.x.x:/opt/metadatatj

# 方式 B: 使用 WinSCP / FileZilla 图形工具
# 连接服务器，上传整个 metadataTJ 目录到 /opt/

# 方式 C: 打包后上传
cd d:\workspace\metadataTJ
tar -czvf metadatatj.tar.gz .
scp metadatatj.tar.gz user@192.168.x.x:/tmp/

# === 在服务器上解压 ===
ssh user@192.168.x.x
cd /opt
mkdir metadatatj
tar -xzvf /tmp/metadatatj.tar.gz -C metadatatj
```

### 3.2 方式二：从内网 Git 仓库克隆

```bash
# 在服务器上执行
cd /opt
git clone http://git.internal.com/metadatatj.git
cd metadatatj
```

### 3.3 方式三：U盘拷贝

```bash
# === 在开发机上 ===
# 1. 打包项目
cd d:\workspace\metadataTJ
tar -czvf metadatatj.tar.gz .

# 2. 复制到U盘
cp metadatatj.tar.gz /media/usb/

# === 在服务器上 ===
# 1. 挂载U盘
mount /dev/sdb1 /mnt/usb

# 2. 复制并解压
cp /mnt/usb/metadatatj.tar.gz /tmp/
cd /opt
mkdir metadatatj
tar -xzvf /tmp/metadatatj.tar.gz -C metadatatj

# 3. 卸载U盘
umount /mnt/usb
```

---

## 四、构建 Docker 镜像

### 4.1 构建镜像

```bash
cd /opt/metadatatj/docker

# 构建镜像
docker build -t metadatatj:latest .

# 构建过程输出
[+] Building 120.5s (15/15) FINISHED
 => [internal] load build definition from Dockerfile
 => [builder 1/5] FROM python:3.11-slim
 => [builder 4/5] RUN pip install -r requirements.txt
 => exporting to image
 => => naming to docker.io/metadatatj:latest
```

**构建时间约 5-10 分钟，取决于网络和硬件。**

### 4.2 验证镜像

```bash
# 查看镜像
docker images metadatatj

# 输出示例
REPOSITORY      TAG       IMAGE ID       CREATED         SIZE
metadatatj      latest    abc123def456   2 minutes ago   500MB
```

### 4.3 镜像标签管理（可选）

```bash
# 添加版本标签
docker tag metadatatj:latest metadatatj:v1.0.0

# 添加日期标签
docker tag metadatatj:latest metadatatj:20240101
```

---

## 五、配置环境变量

### 5.1 创建配置文件

```bash
cd /opt/metadatatj
cp .env.example .env
vim .env
```

### 5.2 完整配置示例

```bash
# ========== 服务端口 ==========
RECOMMEND_PORT=6058
TABLEMAP_PORT=6059
ADMIN_PORT=6060

# ========== 数据源配置 ==========
# 数据源模式: db (数据库) 或 file (文件)
DATA_SOURCE=db

# ========== 主数据库配置 ==========
DB_HOST=192.168.1.100
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=metadata

# ========== 历史数据库配置 ==========
# 如果与主数据库相同，填写相同配置
HISTORY_DB_HOST=192.168.1.100
HISTORY_DB_PORT=3306
HISTORY_DB_USER=root
HISTORY_DB_PASSWORD=your_password
HISTORY_DB_NAME=metadata_history

# ========== LLM 配置 ==========
# 如果内网有大模型服务
LLM_API_BASE=http://192.168.1.200:8000/v1
LLM_API_KEY=your-api-key
LLM_MODEL=qwen-plus
LLM_TIMEOUT=60

# 如果无大模型服务，禁用 LLM 功能
# LLM_DECOMPOSE_ENABLED=false
# LLM_RERANK_ENABLED=false

# ========== Embedding 配置 ==========
# 如果内网有向量服务
EMBEDDING_API_BASE=http://192.168.1.200:8000/v1
EMBEDDING_API_KEY=your-api-key
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_BATCH_SIZE=64

# ========== 推荐配置 ==========
RECALL_TOP_K=30
RERANK_TOP_K=5

# ========== 历史推荐配置 ==========
HISTORY_RECOMMEND_ENABLED=true
HISTORY_SYNC_INTERVAL_HOURS=24
```

### 5.3 最小配置（无大模型）

```bash
# 最小配置 - 仅数据库连接
DATA_SOURCE=db
DB_HOST=192.168.1.100
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=metadata

# 禁用 LLM（使用规则分解和向量分数排序）
LLM_DECOMPOSE_ENABLED=false
LLM_RERANK_ENABLED=false

# 启用历史推荐
HISTORY_RECOMMEND_ENABLED=true
```

---

## 六、启动服务

### 6.1 创建数据目录

```bash
mkdir -p /opt/metadatatj/data
mkdir -p /opt/metadatatj/logs
```

### 6.2 启动容器（完整命令）

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
    --memory 8g \
    --cpus 4 \
    metadatatj:latest all
```

### 6.3 参数说明

| 参数 | 说明 |
|------|------|
| `-d` | 后台运行 |
| `--name metadatatj` | 容器名称 |
| `--restart unless-stopped` | 自动重启策略 |
| `-p 6058:6058` | 推荐服务端口映射 |
| `-v /opt/metadatatj/data:/app/data` | 数据目录挂载 |
| `--env-file .env` | 环境变量文件 |
| `--memory 8g` | 内存限制 |
| `all` | 启动所有服务 |

### 6.4 启动单个服务

```bash
# 仅启动推荐服务
docker run -d \
    --name metadatatj-recommend \
    -p 6058:6058 \
    -v /opt/metadatatj/data:/app/data \
    --env-file /opt/metadatatj/.env \
    metadatatj:latest recommend

# 仅启动表映射服务
docker run -d \
    --name metadatatj-tablemap \
    -p 6059:6059 \
    -v /opt/metadatatj/data:/app/data \
    --env-file /opt/metadatatj/.env \
    metadatatj:latest tablemap

# 仅启动管理后台
docker run -d \
    --name metadatatj-admin \
    -p 6060:6060 \
    --env-file /opt/metadatatj/.env \
    metadatatj:latest admin
```

---

## 七、查看启动日志

### 7.1 实时查看日志

```bash
docker logs -f metadatatj
```

### 7.2 正常启动日志示例

```
========================================
MetadataTJ 启动中...
========================================

检查向量索引...
向量索引不存在，开始构建...

加载知识库...
  - 数据源: 数据库
  - 数据元: 2,156 条
  - 限定词: 523 条

构建向量索引...
  - Embedding 模型: text-embedding-v3
  - 向量维度: 1024
  - 构建进度: 100%
向量索引构建完成

启动所有服务...
  - 推荐服务: 端口 6058
  - 表映射服务: 端口 6059
  - 管理后台: 端口 6060

服务已启动:
  - 推荐服务 PID: 15
  - 表映射服务 PID: 16
  - 管理后台 PID: 17

========================================
启动完成！
========================================
```

### 7.3 查看最近日志

```bash
# 最近 100 行
docker logs --tail 100 metadatatj

# 最近 1 小时
docker logs --since 1h metadatatj
```

---

## 八、验证服务

### 8.1 检查容器状态

```bash
docker ps

# 输出示例
CONTAINER ID   IMAGE              COMMAND         STATUS          PORTS
abc123def456   metadatatj:latest  "./entrypoint…" Up 2 minutes    0.0.0.0:6058-6060->6058-6060/tcp
```

### 8.2 检查健康状态

```bash
docker inspect --format='{{.State.Health.Status}}' metadatatj
# 输出: healthy
```

### 8.3 测试推荐接口

```bash
# 基础测试
curl -X POST http://localhost:6058/autoexport/api/recommend \
    -H "Content-Type: application/json" \
    -d '{"fieldsInfo": []}'

# 完整测试
curl -X POST http://localhost:6058/autoexport/api/recommend \
    -H "Content-Type: application/json" \
    -d '{
        "fieldsInfo": [
            {
                "cname": "姓名",
                "ename": "XM",
                "type": "string",
                "length": 100
            }
        ]
    }'

# 预期返回
{
    "recommendInfos": [
        {
            "element": {
                "cname": ["姓名", "人员姓名", "公民姓名"],
                "ename": ["XM", "RYXM", "GMCXM"],
                "type": ["string", "string", "string"],
                "length": [100, 100, 100],
                "elementCode": ["DE0001", "DE0002", "DE0003"],
                "score": [0.98, 0.95, 0.92],
                "gz": ["", "", ""],
                "gyh": ["", "", ""],
                "mapList": []
            }
        }
    ]
}
```

### 8.4 测试批量推荐

```bash
curl -X POST http://localhost:6058/autoexport/api/recommendBatch \
    -H "Content-Type: application/json" \
    -d '{
        "fieldsInfo": [
            {"cname": "姓名", "ename": "XM"},
            {"cname": "性别", "ename": "XBDM"},
            {"cname": "出生日期", "ename": "CSRQ"}
        ]
    }'
```

### 8.5 测试管理后台

```bash
# 命令行测试
curl http://localhost:6060/

# 浏览器访问
# http://192.168.x.x:6060
```

### 8.6 查看资源使用

```bash
docker stats metadatatj

# 输出示例
CONTAINER     CPU %    MEM USAGE / LIMIT     NET I/O
metadatatj    5.23%    1.5GiB / 8GiB         50MB / 100MB
```

---

## 九、配置开机自启

### 9.1 Docker 服务自启

```bash
systemctl enable docker
```

### 9.2 容器自启

```bash
# 已在启动命令中配置 --restart unless-stopped
# 验证配置
docker inspect metadatatj | grep -A 5 "RestartPolicy"
```

### 9.3 systemd 服务（可选）

```bash
cat > /etc/systemd/system/metadatatj.service << 'EOF'
[Unit]
Description=MetadataTJ Recommendation Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/bin/docker start -a metadatatj
ExecStop=/usr/bin/docker stop metadatatj
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable metadatatj
```

---

## 十、日常运维

### 10.1 查看日志

```bash
# 实时日志
docker logs -f metadatatj

# 最近日志
docker logs --tail 200 metadatatj

# 日志文件
tail -f /opt/metadatatj/logs/recommend.log
tail -f /opt/metadatatj/logs/tablemap.log
```

### 10.2 服务管理

```bash
# 停止服务
docker stop metadatatj

# 启动服务
docker start metadatatj

# 重启服务
docker restart metadatatj

# 优雅停止（等待30秒）
docker stop -t 30 metadatatj
```

### 10.3 更新服务

```bash
# 1. 拉取最新代码
cd /opt/metadatatj
git pull

# 2. 备份旧容器
docker stop metadatatj
docker rename metadatatj metadatatj-backup

# 3. 构建新镜像
cd docker
docker build -t metadatatj:latest .

# 4. 启动新容器
cd /opt/metadatatj
docker run -d \
    --name metadatatj \
    --restart unless-stopped \
    -p 6058:6058 -p 6059:6059 -p 6060:6060 \
    -v /opt/metadatatj/data:/app/data \
    -v /opt/metadatatj/logs:/app/logs \
    --env-file /opt/metadatatj/.env \
    metadatatj:latest all

# 5. 验证成功后删除备份
docker rm metadatatj-backup
```

### 10.4 数据备份

```bash
# 备份向量库
tar -czvf chroma_backup_$(date +%Y%m%d).tar.gz /opt/metadatatj/data/chroma

# 备份配置
cp /opt/metadatatj/.env /backup/metadatatj.env.$(date +%Y%m%d)

# 备份日志
tar -czvf logs_backup_$(date +%Y%m%d).tar.gz /opt/metadatatj/logs
```

### 10.5 数据恢复

```bash
# 停止服务
docker stop metadatatj

# 恢复向量库
tar -xzvf chroma_backup_20240101.tar.gz -C /opt/metadatatj/data/

# 启动服务
docker start metadatatj
```

---

## 十一、故障排查

### 11.1 容器无法启动

```bash
# 查看详细错误
docker logs metadatatj

# 常见错误
```

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `Cannot connect to database` | 数据库连接失败 | 检查 DB_HOST、DB_PASSWORD |
| `Port 6058 already in use` | 端口被占用 | 停止占用端口的服务 |
| `No space left on device` | 磁盘空间不足 | 清理磁盘空间 |
| `Memory allocation failed` | 内存不足 | 增加内存限制 |

### 11.2 推荐返回空结果

```bash
# 检查向量库
ls -la /opt/metadatatj/data/chroma/
# 应有 chroma.sqlite3 文件

# 检查知识库数据
docker exec metadatatj python -c "
from knowledge_loader import load_knowledge
kb = load_knowledge()
print(f'数据元数量: {len(kb.element_items)}')
print(f'限定词数量: {len(kb.determine_items)}')
"

# 如果数据为空，检查数据库
docker exec metadatatj python -c "
import db
rows = db.query_all('SELECT COUNT(*) as cnt FROM rucp_element_biaozhun')
print(f'数据库数据元: {rows[0][\"cnt\"]}')
"
```

### 11.3 向量索引构建失败

```bash
# 查看详细错误
docker logs metadatatj 2>&1 | grep -i "embedding\|chroma"

# 常见原因
# 1. Embedding API 不可达
# 2. 内存不足
# 3. 知识库数据为空

# 手动重建索引
docker exec -it metadatatj python scripts/build_index.py
```

### 11.4 性能问题

```bash
# 查看资源使用
docker stats metadatatj

# 增加资源限制
docker update --memory 8g --memory-swap 8g metadatatj
docker update --cpus 4 metadatatj

# 查看慢查询
docker exec metadatatj cat /app/logs/recommend.log | grep "slow"
```

---

## 十二、完整部署清单

### 部署前检查

- [ ] Docker 已安装并运行
- [ ] Docker 版本 >= 20.10
- [ ] 磁盘空间 >= 10GB
- [ ] 内存 >= 4GB
- [ ] 端口 6058/6059/6060 未被占用
- [ ] 数据库可访问
- [ ] 项目代码已上传

### 部署步骤

- [ ] 1. 检查环境
- [ ] 2. 上传项目代码到 /opt/metadatatj
- [ ] 3. 构建 Docker 镜像
- [ ] 4. 配置 .env 文件
- [ ] 5. 创建数据目录
- [ ] 6. 启动容器
- [ ] 7. 查看启动日志
- [ ] 8. 测试推荐接口
- [ ] 9. 测试管理后台

### 部署后验证

- [ ] 容器状态为 Up
- [ ] 健康检查为 healthy
- [ ] 推荐接口返回正常
- [ ] 管理后台可访问
- [ ] 资源使用正常

---

## 十三、一键部署脚本

```bash
#!/bin/bash
# deploy.sh - 一键部署脚本

set -e

# 配置参数
PROJECT_DIR="${1:-/opt/metadatatj}"
DB_HOST="${2}"
DB_PASSWORD="${3}"
DB_NAME="${4:-metadata}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  MetadataTJ 一键部署"
echo "========================================"
echo ""

# 参数检查
if [ -z "$DB_HOST" ] || [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}用法: $0 <项目目录> <数据库地址> <数据库密码> [数据库名]${NC}"
    echo "示例: $0 /opt/metadatatj 192.168.1.100 mypassword metadata"
    exit 1
fi

echo "项目目录: $PROJECT_DIR"
echo "数据库地址: $DB_HOST"
echo "数据库名: $DB_NAME"
echo ""

# 1. 检查 Docker
echo -e "${YELLOW}[1/8] 检查 Docker 环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    echo "请先安装 Docker: https://docs.docker.com/engine/install/"
    exit 1
fi
echo "Docker 版本: $(docker --version)"

# 2. 检查端口
echo -e "${YELLOW}[2/8] 检查端口...${NC}"
for port in 6058 6059 6060; do
    if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        echo -e "${RED}错误: 端口 $port 已被占用${NC}"
        exit 1
    fi
done
echo "端口检查通过"

# 3. 检查磁盘空间
echo -e "${YELLOW}[3/8] 检查磁盘空间...${NC}"
AVAILABLE=$(df -BG /opt | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$AVAILABLE" -lt 10 ]; then
    echo -e "${RED}错误: 磁盘空间不足 (当前 ${AVAILABLE}GB，需要 10GB)${NC}"
    exit 1
fi
echo "磁盘空间: ${AVAILABLE}GB"

# 4. 构建镜像
echo -e "${YELLOW}[4/8] 构建 Docker 镜像...${NC}"
cd "$PROJECT_DIR/docker"
docker build -t metadatatj:latest .
echo "镜像构建完成"

# 5. 配置环境变量
echo -e "${YELLOW}[5/8] 配置环境变量...${NC}"
cd "$PROJECT_DIR"
cat > .env << EOF
# 服务端口
RECOMMEND_PORT=6058
TABLEMAP_PORT=6059
ADMIN_PORT=6060

# 数据源配置
DATA_SOURCE=db

# 主数据库
DB_HOST=$DB_HOST
DB_PORT=3306
DB_USER=root
DB_PASSWORD=$DB_PASSWORD
DB_NAME=$DB_NAME

# 历史数据库
HISTORY_DB_HOST=$DB_HOST
HISTORY_DB_PORT=3306
HISTORY_DB_USER=root
HISTORY_DB_PASSWORD=$DB_PASSWORD
HISTORY_DB_NAME=metadata_history

# LLM 配置（默认禁用）
LLM_DECOMPOSE_ENABLED=false
LLM_RERANK_ENABLED=false

# 推荐配置
RECALL_TOP_K=30
RERANK_TOP_K=5

# 历史推荐配置
HISTORY_RECOMMEND_ENABLED=true
HISTORY_SYNC_INTERVAL_HOURS=24
EOF
echo "配置文件已创建"

# 6. 创建数据目录
echo -e "${YELLOW}[6/8] 创建数据目录...${NC}"
mkdir -p "$PROJECT_DIR"/{data,logs}
echo "目录创建完成"

# 7. 启动容器
echo -e "${YELLOW}[7/8] 启动容器...${NC}"
docker stop metadatatj 2>/dev/null || true
docker rm metadatatj 2>/dev/null || true

docker run -d \
    --name metadatatj \
    --restart unless-stopped \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    -v "$PROJECT_DIR/data:/app/data" \
    -v "$PROJECT_DIR/logs:/app/logs" \
    --env-file "$PROJECT_DIR/.env" \
    --memory 8g \
    --cpus 4 \
    metadatatj:latest all

echo "容器已启动"

# 8. 等待并验证
echo -e "${YELLOW}[8/8] 等待服务启动...${NC}"
sleep 15

# 验证
echo ""
echo "验证服务状态..."
if docker ps | grep -q metadatatj; then
    echo -e "${GREEN}✅ 部署成功！${NC}"
    echo ""
    echo "========================================"
    echo "  服务信息"
    echo "========================================"
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo "服务器地址: $SERVER_IP"
    echo ""
    echo "服务端口:"
    echo "  - 推荐服务: http://$SERVER_IP:6058"
    echo "  - 表映射服务: http://$SERVER_IP:6059"
    echo "  - 管理后台: http://$SERVER_IP:6060"
    echo ""
    echo "测试命令:"
    echo "  curl -X POST http://$SERVER_IP:6058/autoexport/api/recommend \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"fieldsInfo\": [{\"cname\": \"姓名\", \"ename\": \"XM\"}]}'"
    echo ""
    echo "查看日志:"
    echo "  docker logs -f metadatatj"
else
    echo -e "${RED}❌ 部署失败${NC}"
    echo ""
    echo "查看错误日志:"
    docker logs metadatatj
    exit 1
fi
```

**使用方法**:

```bash
# 上传脚本到服务器
scp deploy.sh user@192.168.x.x:/tmp/

# 执行部署
ssh user@192.168.x.x
chmod +x /tmp/deploy.sh
/tmp/deploy.sh /opt/metadatatj 192.168.1.100 your_password metadata
```

---

## 十四、快速操作总结

```bash
# === 完整流程 ===

# 1. 上传代码
scp -r d:\workspace\metadataTJ user@192.168.x.x:/opt/metadatatj

# 2. SSH 登录
ssh user@192.168.x.x

# 3. 构建镜像
cd /opt/metadatatj/docker
docker build -t metadatatj:latest .

# 4. 配置环境
cd /opt/metadatatj
cp .env.example .env
vim .env  # 配置数据库

# 5. 启动服务
mkdir -p /opt/metadatatj/{data,logs}
docker run -d \
    --name metadatatj \
    --restart unless-stopped \
    -p 6058:6058 -p 6059:6059 -p 6060:6060 \
    -v /opt/metadatatj/data:/app/data \
    -v /opt/metadatatj/logs:/app/logs \
    --env-file /opt/metadatatj/.env \
    metadatatj:latest all

# 6. 验证
docker logs -f metadatatj
curl -X POST http://localhost:6058/autoexport/api/recommend \
    -H "Content-Type: application/json" \
    -d '{"fieldsInfo": [{"cname": "姓名", "ename": "XM"}]}'
```

**预计部署时间：15-20 分钟**
