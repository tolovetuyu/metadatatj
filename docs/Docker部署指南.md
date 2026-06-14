# MetadataTJ Docker 部署指南

## 一、概述

本文档介绍如何使用 Docker 部署 MetadataTJ 推荐服务，解决现场安装时缺少依赖的问题。

### 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker 容器                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 推荐服务     │  │ 表映射服务   │  │ 管理后台     │         │
│  │ 端口 6058   │  │ 端口 6059   │  │ 端口 6060   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                   │
│  ┌───────────────────────┴───────────────────────┐         │
│  │              共享数据卷                          │         │
│  │  - /app/data      向量库数据                    │         │
│  │  - /app/logs      日志文件                      │         │
│  │  - /app/knowledge 知识库文件                    │         │
│  └─────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、前置条件

### 2.1 软件要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Docker | >= 20.10 | 容器运行时 |
| Docker Compose | >= 2.0 | 多容器编排（可选） |

### 2.2 硬件要求

| 资源 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2核 | 4核 |
| 内存 | 4GB | 8GB |
| 磁盘 | 10GB | 20GB |

### 2.3 安装 Docker

**CentOS/RHEL**
```bash
# 安装 Docker
yum install -y yum-utils
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io

# 启动 Docker
systemctl start docker
systemctl enable docker
```

**Ubuntu/Debian**
```bash
# 安装 Docker
apt-get update
apt-get install -y ca-certificates curl gnupg
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io

# 启动 Docker
systemctl start docker
systemctl enable docker
```

**Windows**
```powershell
# 下载并安装 Docker Desktop
# https://www.docker.com/products/docker-desktop
```

---

## 三、快速部署

### 3.1 获取项目

```bash
# 克隆项目（或复制项目目录）
git clone <repository-url> metadatatj
cd metadatatj
```

### 3.2 配置数据源

**推荐：数据库模式**（无需知识库文件）

数据从数据库表读取：
- `rucp_element_biaozhun` - 数据元
- `rucp_element_determiner` - 限定词
- `rucp_standard_dataset` - 标准表
- `rucp_standard_dataset_field` - 表字段

```bash
# 配置环境变量
export DATA_SOURCE=db
export DB_HOST=192.168.1.100
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=password
export DB_NAME=metadata
```

**备选：文件模式**（需要知识库文件）

将知识库文件放入 `knowledge/` 目录：

```
knowledge/
├── 01_公安标准数据元和限定词_v2.xlsx
├── 01_标准库数据集.xlsx
└── dict/
    ├── table_code_f.csv
    └── df_api.npy
```

### 3.3 构建镜像

```bash
cd docker

# 构建镜像
docker build -t metadatatj:latest .
```

### 3.4 启动服务

**推荐：数据库模式**
```bash
docker run -d \
    --name metadatatj \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    -v $(pwd)/../data:/app/data \
    -v $(pwd)/../logs:/app/logs \
    -e DATA_SOURCE=db \
    -e DB_HOST=192.168.1.100 \
    -e DB_PORT=3306 \
    -e DB_USER=root \
    -e DB_PASSWORD=password \
    -e DB_NAME=metadata \
    -e LLM_API_KEY=your_api_key \
    -e LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
    metadatatj:latest all
```

**备选：文件模式**
```bash
docker run -d \
    --name metadatatj \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    -v $(pwd)/../data:/app/data \
    -v $(pwd)/../logs:/app/logs \
    -v $(pwd)/../knowledge:/app/knowledge \
    -e DATA_SOURCE=file \
    -e LLM_API_KEY=your_api_key \
    -e LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
    metadatatj:latest all
```

**使用 Docker Compose**
```bash
# 创建环境变量文件
cat > .env << EOF
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DATA_SOURCE=file
EOF

# 启动所有服务
docker-compose --profile all-in-one up -d all-in-one

# 或分别启动各服务
docker-compose up -d recommend tablemap admin
```

### 3.5 验证服务

```bash
# 检查容器状态
docker ps

# 测试推荐接口
curl -X POST http://localhost:6058/autoexport/api/recommend \
    -H "Content-Type: application/json" \
    -d '{"fieldsInfo": [{"cname": "姓名", "ename": "XM"}]}'

# 查看日志
docker logs metadatatj
```

---

## 四、配置说明

### 4.1 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| **服务配置** |||
| RECOMMEND_PORT | 6058 | 推荐服务端口 |
| TABLEMAP_PORT | 6059 | 表映射服务端口 |
| ADMIN_PORT | 6060 | 管理后台端口 |
| **数据源配置** |||
| DATA_SOURCE | file | 数据源模式 (file/db) |
| **LLM配置** |||
| LLM_API_KEY | - | LLM API密钥 |
| LLM_BASE_URL | dashscope | LLM API地址 |
| LLM_DECOMPOSE_ENABLED | true | 启用LLM分解 |
| LLM_RERANK_ENABLED | true | 启用LLM精排 |
| **数据库配置** |||
| DB_HOST | localhost | 主数据库地址 |
| DB_PORT | 3306 | 主数据库端口 |
| DB_USER | root | 主数据库用户 |
| DB_PASSWORD | - | 主数据库密码 |
| DB_NAME | metadata | 主数据库名 |
| **历史数据库配置** |||
| HISTORY_DB_HOST | localhost | 历史数据库地址 |
| HISTORY_DB_PORT | 3306 | 历史数据库端口 |
| HISTORY_DB_USER | root | 历史数据库用户 |
| HISTORY_DB_PASSWORD | - | 历史数据库密码 |
| HISTORY_DB_NAME | metadata_history | 历史数据库名 |
| **历史推荐配置** |||
| HISTORY_RECOMMEND_ENABLED | false | 启用历史推荐 |
| HISTORY_SYNC_INTERVAL_HOURS | 24 | 同步间隔(小时) |

### 4.2 数据卷

| 容器路径 | 说明 |
|---------|------|
| /app/data | 向量库数据（ChromaDB） |
| /app/logs | 日志文件 |
| /app/knowledge | 知识库文件（Excel/CSV） |

### 4.3 端口映射

| 容器端口 | 服务 | 说明 |
|---------|------|------|
| 6058 | 推荐服务 | 数据元/限定词推荐 |
| 6059 | 表映射服务 | 表/字段映射 |
| 6060 | 管理后台 | Web管理界面 |

---

## 五、部署模式

### 5.1 单容器模式（推荐）

所有服务运行在一个容器中，适合中小规模部署。

```bash
docker run -d \
    --name metadatatj \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    -v /data/metadatatj/data:/app/data \
    -v /data/metadatatj/logs:/app/logs \
    -v /data/metadatatj/knowledge:/app/knowledge \
    -e LLM_API_KEY=your_api_key \
    metadatatj:latest all
```

### 5.2 多容器模式

各服务独立运行，适合大规模部署或需要独立扩展的场景。

```bash
# 推荐服务
docker run -d --name metadatatj-recommend \
    -p 6058:6058 \
    -v /data/metadatatj/data:/app/data \
    -v /data/metadatatj/knowledge:/app/knowledge \
    -e LLM_API_KEY=your_api_key \
    metadatatj:latest recommend

# 表映射服务
docker run -d --name metadatatj-tablemap \
    -p 6059:6059 \
    -v /data/metadatatj/data:/app/data \
    -v /data/metadatatj/knowledge:/app/knowledge \
    metadatatj:latest tablemap

# 管理后台
docker run -d --name metadatatj-admin \
    -p 6060:6060 \
    -v /data/metadatatj/data:/app/data \
    -v /data/metadatatj/knowledge:/app/knowledge \
    metadatatj:latest admin
```

### 5.3 数据库模式

从数据库读取知识库数据。

```bash
docker run -d \
    --name metadatatj \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    -v /data/metadatatj/data:/app/data \
    -e DATA_SOURCE=db \
    -e DB_HOST=192.168.1.100 \
    -e DB_PORT=3306 \
    -e DB_USER=root \
    -e DB_PASSWORD=password \
    -e DB_NAME=metadata \
    -e LLM_API_KEY=your_api_key \
    metadatatj:latest all
```

---

## 六、运维操作

### 6.1 启动/停止服务

```bash
# 启动
docker start metadatatj

# 停止
docker stop metadatatj

# 重启
docker restart metadatatj

# 优雅停止（等待请求处理完成）
docker stop -t 30 metadatatj
```

### 6.2 查看日志

```bash
# 查看全部日志
docker logs metadatatj

# 实时查看日志
docker logs -f metadatatj

# 查看最近100行
docker logs --tail 100 metadatatj

# 查看指定时间范围
docker logs --since "2024-01-01" --until "2024-01-02" metadatatj
```

### 6.3 进入容器

```bash
# 进入容器终端
docker exec -it metadatatj bash

# 执行单条命令
docker exec metadatatj python -c "print('hello')"
```

### 6.4 更新服务

```bash
# 1. 停止旧容器
docker stop metadatatj
docker rename metadatatj metadatatj-old

# 2. 构建新镜像
docker build -t metadatatj:latest .

# 3. 启动新容器
docker run -d --name metadatatj \
    -p 6058:6058 -p 6059:6059 -p 6060:6060 \
    -v /data/metadatatj/data:/app/data \
    -v /data/metadatatj/logs:/app/logs \
    -v /data/metadatatj/knowledge:/app/knowledge \
    metadatatj:latest all

# 4. 验证无误后删除旧容器
docker rm metadatatj-old
```

### 6.5 备份与恢复

**备份数据**
```bash
# 备份向量库
tar -czvf chroma_backup_$(date +%Y%m%d).tar.gz /data/metadatatj/data/chroma

# 备份知识库
tar -czvf knowledge_backup_$(date +%Y%m%d).tar.gz /data/metadatatj/knowledge
```

**恢复数据**
```bash
# 恢复向量库
tar -xzvf chroma_backup_20240101.tar.gz -C /data/metadatatj/data/

# 恢复知识库
tar -xzvf knowledge_backup_20240101.tar.gz -C /data/metadatatj/
```

### 6.6 重建向量索引

```bash
# 进入容器重建索引
docker exec -it metadatatj python scripts/build_index.py

# 或启动时自动重建
docker run --rm \
    -v /data/metadatatj/data:/app/data \
    -v /data/metadatatj/knowledge:/app/knowledge \
    metadatatj:latest build-index
```

---

## 七、监控与健康检查

### 7.1 健康检查

Dockerfile 已配置健康检查，可通过以下命令查看：

```bash
# 查看健康状态
docker inspect --format='{{.State.Health.Status}}' metadatatj

# 查看健康检查历史
docker inspect --format='{{json .State.Health}}' metadatatj | jq
```

### 7.2 资源监控

```bash
# 查看资源使用
docker stats metadatatj

# 查看详细信息
docker inspect metadatatj
```

### 7.3 Prometheus 监控（可选）

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'metadatatj'
    static_configs:
      - targets: ['localhost:6058', 'localhost:6059', 'localhost:6060']
```

---

## 八、常见问题

### 8.1 容器无法启动

**问题**：容器启动后立即退出

**排查**：
```bash
# 查看日志
docker logs metadatatj

# 常见原因：
# 1. 知识库文件缺失 - 检查 knowledge/ 目录
# 2. LLM API 配置错误 - 检查 LLM_API_KEY
# 3. 端口被占用 - 检查端口占用情况
```

### 8.2 向量索引构建失败

**问题**：启动时报错 "向量索引不存在"

**解决**：
```bash
# 手动构建索引
docker exec -it metadatatj python scripts/build_index.py
```

### 8.3 内存不足

**问题**：容器因内存不足被 OOM Kill

**解决**：
```bash
# 增加内存限制
docker update --memory 8g --memory-swap 8g metadatatj

# 或启动时指定
docker run -d --memory 8g --memory-swap 8g ...
```

### 8.4 无法连接数据库

**问题**：DATA_SOURCE=db 时连接失败

**解决**：
```bash
# 检查网络连通性
docker exec metadatatj ping DB_HOST

# 使用 host.docker.internal 访问宿主机
-e DB_HOST=host.docker.internal

# 或使用宿主机IP
-e DB_HOST=192.168.1.100
```

### 8.5 Windows 路径问题

**问题**：Windows 下挂载路径错误

**解决**：
```powershell
# 使用绝对路径
docker run -v C:/data/metadatatj/data:/app/data ...

# 或使用 ${PWD}
docker run -v ${PWD}/data:/app/data ...
```

---

## 九、生产环境建议

### 9.1 安全配置

```bash
# 1. 使用非 root 用户运行（Dockerfile 已配置）
# 2. 限制容器能力
docker run --cap-drop ALL --cap-add NET_BIND_SERVICE ...

# 3. 只读根文件系统
docker run --read-only --tmpfs /tmp ...

# 4. 限制资源
docker run --memory 4g --cpus 2 ...
```

### 9.2 日志管理

```bash
# 配置日志驱动和轮转
docker run \
    --log-driver json-file \
    --log-opt max-size=100m \
    --log-opt max-file=10 \
    ...
```

### 9.3 自动重启

```bash
# 配置重启策略
docker run --restart unless-stopped ...
```

### 9.4 使用 systemd 管理

```ini
# /etc/systemd/system/metadatatj.service
[Unit]
Description=MetadataTJ Service
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
```

```bash
# 启用服务
systemctl enable metadatatj
systemctl start metadatatj
```

---

## 十、附录

### 10.1 完整启动命令示例

```bash
# 生产环境启动命令
docker run -d \
    --name metadatatj \
    --restart unless-stopped \
    --memory 8g \
    --cpus 4 \
    -p 6058:6058 \
    -p 6059:6059 \
    -p 6060:6060 \
    -v /data/metadatatj/data:/app/data \
    -v /data/metadatatj/logs:/app/logs \
    -v /data/metadatatj/knowledge:/app/knowledge \
    -e DATA_SOURCE=file \
    -e LLM_API_KEY=sk-xxx \
    -e LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
    -e LLM_DECOMPOSE_ENABLED=true \
    -e LLM_RERANK_ENABLED=true \
    -e HISTORY_RECOMMEND_ENABLED=true \
    -e HISTORY_DB_HOST=192.168.1.100 \
    -e HISTORY_DB_PORT=3306 \
    -e HISTORY_DB_USER=root \
    -e HISTORY_DB_PASSWORD=password \
    -e HISTORY_DB_NAME=metadata_history \
    --log-driver json-file \
    --log-opt max-size=100m \
    --log-opt max-file=10 \
    metadatatj:latest all
```

### 10.2 Docker Compose 完整示例

```yaml
version: "3.8"

services:
  metadatatj:
    image: metadatatj:latest
    container_name: metadatatj
    restart: unless-stopped
    ports:
      - "6058:6058"
      - "6059:6059"
      - "6060:6060"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./knowledge:/app/knowledge
    environment:
      - DATA_SOURCE=file
      - LLM_API_KEY=sk-xxx
      - LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
      - HISTORY_RECOMMEND_ENABLED=true
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "10"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6058/autoexport/api/recommend", "-X", "POST", "-H", "Content-Type: application/json", "-d", "{\"fieldsInfo\":[]}"]
      interval: 30s
      timeout: 10s
      retries: 3
```
