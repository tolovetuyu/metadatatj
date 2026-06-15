# MetadataTJ Docker 部署安装配置手册

## 一、系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | CentOS 7+ / Ubuntu 18.04+ |
| Docker | 20.10+ |
| 内存 | ≥ 4GB |
| 磁盘 | ≥ 10GB |
| 网络 | 内网环境可运行（详见离线模式说明） |

---

## 二、目录结构

```
metadataTJ/
├── docker/
│   ├── Dockerfile              # 镜像构建文件
│   ├── docker-compose.yml      # 编排配置
│   └── entrypoint.sh           # 容器入口脚本
├── src/
│   ├── config.py               # 配置加载
│   ├── db.py                   # 数据库连接
│   ├── app_recommend.py        # 推荐服务（端口 6058）
│   ├── app_tablemap.py         # 表映射服务（端口 6061）
│   ├── app_admin.py            # 管理后台（端口 6070）
│   ├── services/
│   │   ├── recommender.py      # 推荐核心逻辑
│   │   ├── history_sync.py     # 历史数据同步
│   │   ├── history_recommender.py  # 历史推荐缓存
│   │   ├── common_fields.py    # RUN 通用字段
│   │   ├── knowledge_loader.py # 知识库加载
│   │   └── scheduler.py        # 定时任务调度
│   ├── llm/                    # LLM 相关（分解、精排）
│   ├── vector/                 # 向量库封装（ChromaDB）
│   └── rules/                  # 规则引擎
├── scripts/
│   └── build_index.py          # 向量索引构建脚本
├── data/
│   └── chroma/                 # ChromaDB 持久化目录
├── knowledge/                  # 知识库文件
├── logs/                       # 日志目录
├── .env                        # 环境变量配置
└── docs/
    └── migration_add_determiner_codes.sql  # 数据库迁移脚本
```

---

## 三、镜像构建

```bash
cd metadataTJ
docker build -t metadatatj:latest -f docker/Dockerfile .
```

---

## 四、数据库准备

### 4.1 执行迁移脚本

在 `metadata_history` 数据库上执行迁移脚本，为统计表添加限定词编码字段：

```bash
mysql -h <数据库地址> -u <用户名> -p metadata_history < docs/migration_add_determiner_codes.sql
```

迁移内容：
- 为 `rucp_history_recommend_stat` 表添加 `determiner1_code`、`determiner2_code` 字段
- 更新唯一键，纳入限定词编码，支持同一来源+数据元对应不同限定词组合

### 4.2 确认源数据

`rucp_task_process` 表需存在于历史库中，包含 `position='fast_handle'` 的人工对标 JSON 数据。

---

## 五、配置说明（.env）

### 5.1 服务端口

```bash
RECOMMEND_HOST=0.0.0.0
RECOMMEND_PORT=6058
TABLEMAP_HOST=0.0.0.0
TABLEMAP_PORT=6061
ADMIN_HOST=0.0.0.0
ADMIN_PORT=6070
```

### 5.2 数据库配置

```bash
# 主数据库（数据元、限定词、标准表目录）
DATA_SOURCE=db
DB_HOST=<主库地址>
DB_PORT=3306
DB_USER=<用户名>
DB_PASSWORD=<密码>
DB_NAME=metadata
DB_CHARSET=utf8mb4

# 历史数据库（统计表、对标过程表、同步状态表）
HISTORY_DB_HOST=<历史库地址>
HISTORY_DB_PORT=3306
HISTORY_DB_USER=<用户名>
HISTORY_DB_PASSWORD=<密码>
HISTORY_DB_NAME=metadata_history
HISTORY_DB_CHARSET=utf8mb4
```

> `rucp_task_process` 表与历史库同库，无需额外配置数据库连接。

### 5.3 历史推荐配置

```bash
# 启用历史推荐优先匹配（必须为 true 才会使用历史数据）
HISTORY_RECOMMEND_ENABLED=true
# 历史推荐统计表
HISTORY_RECOMMEND_TABLE=rucp_history_recommend_stat
# 历史对标记录表
HISTORY_SOURCE_TABLE=rucp_element_mapping_history
# 同步间隔（小时）
HISTORY_SYNC_INTERVAL_HOURS=24
# 人工对标过程表
TASK_PROCESS_TABLE=rucp_task_process
```

### 5.4 大模型与 Embedding 配置

#### 联网模式

```bash
LLM_API_BASE=http://<LLM服务地址>:8888
LLM_API_KEY=<密钥>
LLM_MODEL=<模型名>
LLM_DECOMPOSE_ENABLED=true
LLM_RERANK_ENABLED=true

EMBEDDING_API_BASE=http://<Embedding服务地址>:8888
EMBEDDING_API_KEY=<密钥>
EMBEDDING_MODEL=<模型名>
```

#### 内网离线模式

```bash
LLM_DECOMPOSE_ENABLED=false
LLM_RERANK_ENABLED=false
```

> 关闭 LLM 后：语义分解走规则兜底，精排走向量分兜底。推荐完全依赖历史数据+规则。

### 5.5 检索参数

```bash
RECALL_TOP_K=30           # 向量召回数量
RERANK_TOP_K=5            # 精排返回数量
TABLE_MATCH_THRESHOLD=0.75
FIELD_MATCH_THRESHOLD=0.80
```

---

## 六、部署运行

### 6.1 Docker 运行

```bash
docker run -d \
  --name metadatatj \
  --restart unless-stopped \
  -p 6058:6058 \
  -v /opt/metadataTJ/data:/app/data \
  -v /opt/metadataTJ/logs:/app/logs \
  -v /opt/metadataTJ/knowledge:/app/knowledge \
  --env-file .env \
  metadatatj:latest recommend
```

### 6.2 Docker Compose 运行

```bash
docker-compose up -d recommend
```

### 6.3 更新代码到运行中容器

```bash
# 需要更新的文件
docker cp src/config.py <容器名>:/app/src/config.py
docker cp src/db.py <容器名>:/app/src/db.py
docker cp src/app_recommend.py <容器名>:/app/src/app_recommend.py
docker cp src/services/recommender.py <容器名>:/app/src/services/recommender.py
docker cp src/services/history_sync.py <容器名>:/app/src/services/history_sync.py
docker cp src/services/history_recommender.py <容器名>:/app/src/services/history_recommender.py
docker cp src/services/scheduler.py <容器名>:/app/src/services/scheduler.py
docker cp src/services/knowledge_loader.py <容器名>:/app/src/services/knowledge_loader.py
docker cp .env <容器名>:/app/.env

# 重启生效
docker restart <容器名>
```

---

## 七、向量索引构建

### 7.1 联网环境（容器内可访问 Embedding API）

```bash
docker exec -w /app <容器名> python scripts/build_index.py
```

### 7.2 内网环境（外网构建 + 拷贝）

在可访问 Embedding API 的外网机器上：

```bash
# 1. 构建索引
cd metadataTJ
python scripts/build_index.py

# 2. 将 data/chroma 目录拷贝到内网服务器

# 3. 拷贝进容器
docker cp data/chroma/. <容器名>:/app/data/chroma/

# 4. 重启
docker restart <容器名>
```

> 无向量索引时服务仍可运行，推荐走纯历史模式（需 `HISTORY_RECOMMEND_ENABLED=true` 且已同步数据）。

---

## 八、首次数据同步

### 8.1 从 rucp_task_process 同步（主要数据源）

```bash
curl -X POST http://<服务地址>:6058/autoexport/api/history/sync \
  -H 'Content-Type: application/json' \
  -d '{"force_full": true, "source": "task_process"}'
```

### 8.2 从 rucp_element_mapping_history 同步（备用数据源）

```bash
curl -X POST http://<服务地址>:6058/autoexport/api/history/sync \
  -H 'Content-Type: application/json' \
  -d '{"force_full": true, "source": "mapping_history"}'
```

### 8.3 同步参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| force_full | true / false | 全量同步 / 增量同步 |
| source | task_process | 从 rucp_task_process JSON 解析同步 |
| source | mapping_history | 从 rucp_element_mapping_history 平铺表同步 |
| source | all | 两个数据源都同步 |

### 8.4 验证同步结果

```bash
# 查看缓存统计
curl http://<服务地址>:6058/autoexport/api/history/stats
```

返回示例：
```json
{"source_count": 5, "total_records": 25, "loaded": true}
```

---

## 九、接口说明

### 9.1 推荐接口

```
POST /autoexport/api/recommendWithExtend
Content-Type: application/json

{
  "lybEname": "",
  "fieldsInfo": [
    {"cname": "姓名", "ename": "name", "type": "string", "length": 255},
    {"cname": "证件", "ename": "idcard", "type": "string", "length": 255}
  ]
}
```

### 9.2 通用字段接口

```
POST /autoexport/api/commonFields
Content-Type: application/json

{
  "primaryKeyFields": ["id", "name"],
  "RUN_SJLYXTFLDM": "01001",
  "RUN_CJD_XZQHDM": "610000",
  "RUN_SJJLMGJB": "99"
}
```

### 9.3 历史同步接口

```
POST /autoexport/api/history/sync
Content-Type: application/json

{"force_full": true, "source": "task_process"}
```

### 9.4 历史统计接口

```
GET /autoexport/api/history/stats
```

---

## 十、运行模式对比

| 模式 | LLM | Embedding | ChromaDB | 历史数据 | 推荐质量 |
|------|-----|-----------|----------|----------|----------|
| 全功能 | ✅ | ✅ | ✅ | ✅ | 最优 |
| 无LLM | ❌ | ✅ | ✅ | ✅ | 良好（规则分解+向量召回+历史优先） |
| 纯历史 | ❌ | ❌ | ❌ | ✅ | 可用（仅历史匹配，无历史时无推荐） |
| 无历史 | ✅ | ✅ | ✅ | ❌ | 良好（LLM+向量，无限定词复用） |

---

## 十一、数据流说明

```
┌─────────────────────────────────────────────────────────────────────┐
│                        推荐请求                                     │
│                 POST /autoexport/api/recommendWithExtend             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │ 1. 历史推荐缓存查询      │  source_cname → 历史匹配结果
              │    （内存缓存，最高优先级）│  包含 element_code + 限定词编码
              └────────────┬────────────┘
                           │
           ┌───────────────┼───────────────┐
           │ 有历史结果     │               │ 无历史结果
           ▼               │               ▼
  ┌─────────────────┐      │      ┌─────────────────┐
  │ 直接使用历史结果  │      │      │ 规则分解 + 向量召回│
  │ 数据元详情回查    │      │      │ + LLM精排（可选） │
  │ 限定词直接复用    │      │      └────────┬────────┘
  └─────────────────┘      │               │
                           │               │
              ┌────────────▼────────────────▼┐
              │     2. 合并候选 + 构建响应      │
              └────────────┬─────────────────┘
                           │
              ┌────────────▼─────────────┐
              │ 3. 限定词推荐              │
              │  有历史限定词 → 直接复用    │  determiner1_code / determiner2_code
              │  无历史限定词 → LLM+向量   │  回查 ChromaDB 获取 cn_name
              └──────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        同步数据流                                    │
│                                                                     │
│  rucp_task_process (position=fast_handle)                           │
│  ┌──────────────────────────────────┐                               │
│  │ JSON: handle.strategy            │                               │
│  │   sourceId → interalcode         │                               │
│  │   determiner1 / determiner2      │                               │
│  └──────────────┬───────────────────┘                               │
│                 │ sync_from_task_process()                           │
│                 ▼                                                    │
│  rucp_history_recommend_stat                                        │
│  ┌──────────────────────────────────┐                               │
│  │ source_cname + target_element_   │                               │
│  │ code + determiner1_code +        │                               │
│  │ determiner2_code + match_count   │                               │
│  └──────────────┬───────────────────┘                               │
│                 │ load_cache()                                       │
│                 ▼                                                    │
│  内存缓存: {source_cname → [HistoryRecommend, ...]}                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 十二、故障排查

### 服务启动后推荐返回空值

1. 检查历史推荐是否启用：`HISTORY_RECOMMEND_ENABLED=true`
2. 检查是否已同步数据：`GET /autoexport/api/history/stats`
3. 检查 ChromaDB 是否有数据：`docker exec <容器名> ls /app/data/chroma/`

### 同步接口返回 0 条记录

1. 确认 `rucp_task_process` 表有 `position='fast_handle'` 的数据
2. 确认历史库连接正确：检查 `HISTORY_DB_*` 配置
3. 手动指定 source 参数：`"source": "task_process"`

### 数据库连接失败

1. 容器内验证：`docker exec <容器名> python -c "import pymysql; pymysql.connect(host='地址', port=3306, user='用户名', password='密码', database='库名')"`
2. 注意容器内访问宿主机用 `host.docker.internal` 或宿主机内网 IP

### 限定词未复用

1. 确认统计表有 `determiner1_code`/`determiner2_code` 数据：`SELECT * FROM rucp_history_recommend_stat WHERE determiner1_code != '' LIMIT 5`
2. 确认迁移脚本已执行（字段不存在会报错）
3. 重新全量同步：`POST /autoexport/api/history/sync {"force_full": true, "source": "task_process"}`

### ChromaDB 为空且无外网

参考「七、向量索引构建 - 7.2 内网环境」在外网构建后拷贝。或使用纯历史模式（`LLM_DECOMPOSE_ENABLED=false` + `LLM_RERANK_ENABLED=false`），无需 ChromaDB。
