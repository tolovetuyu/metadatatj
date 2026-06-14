-- ============================================================
-- MetadataTJ 数据库初始化脚本
-- ============================================================
-- 执行前请先创建数据库
-- CREATE DATABASE metadata DEFAULT CHARACTER SET utf8mb4;
-- CREATE DATABASE metadata_history DEFAULT CHARACTER SET utf8mb4;
-- ============================================================

-- ============================================================
-- 1. 主数据库表结构 (metadata)
-- ============================================================

-- --------------------------------------------------------
-- 1.1 数据元标准表 (rucp_element_biaozhun)
-- --------------------------------------------------------
-- 数据元标准表，存储标准数据元定义
-- 注意：如果已有，请忽略此表
CREATE TABLE IF NOT EXISTS rucp_element_biaozhun (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) NOT NULL COMMENT '数据元代码',
    chname VARCHAR(200) NOT NULL COMMENT '中文名称',
    enname VARCHAR(200) COMMENT '英文名称',
    type VARCHAR(50) COMMENT '类型',
    length VARCHAR(50) COMMENT '长度',
    classify VARCHAR(50) COMMENT '分类',
    state VARCHAR(2) DEFAULT '1' COMMENT '状态',
    up_to_date VARCHAR(2) DEFAULT '1' COMMENT '是否最新',
    createtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据元标准表';

-- --------------------------------------------------------
-- 1.2 限定词表 (rucp_element_determiner)
-- --------------------------------------------------------
-- 限定词表，存储标准限定词定义
-- 注意：如果已有，请忽略此表
CREATE TABLE IF NOT EXISTS rucp_element_determiner (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) NOT NULL COMMENT '限定词代码',
    chname VARCHAR(200) NOT NULL COMMENT '中文名称',
    enname VARCHAR(200) COMMENT '英文名称',
    interalcode VARCHAR(100) COMMENT '内部代码',
    status VARCHAR(2) DEFAULT '1' COMMENT '状态',
    createtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='限定词表';

-- --------------------------------------------------------
-- 1.3 历史对标记录表 (rucp_element_mapping_history)
-- --------------------------------------------------------
-- 历史对标记录表，存储历史人工对标数据（数据来源）
-- 此表由其他系统或人工产生，本项目仅读取
CREATE TABLE IF NOT EXISTS rucp_element_mapping_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_cname VARCHAR(200) NOT NULL COMMENT '来源字段中文名',
    source_ename VARCHAR(200) COMMENT '来源字段英文名',
    target_element_code VARCHAR(100) COMMENT '目标数据元代码',
    target_cn_name VARCHAR(200) COMMENT '目标数据元中文名',
    target_en_name VARCHAR(200) COMMENT '目标数据元英文名',
    target_type VARCHAR(50) COMMENT '目标数据类型',
    target_length VARCHAR(50) COMMENT '目标数据长度',
    target_classify VARCHAR(50) COMMENT '目标分类',
    determiner VARCHAR(100) COMMENT '限定词',
    status VARCHAR(2) DEFAULT '1' COMMENT '状态',
    update_time DATETIME COMMENT '更新时间',
    createtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_source (source_cname, target_element_code),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史对标记录表';


-- ============================================================
-- 2. 历史数据库表结构 (metadata_history)
-- ============================================================

-- --------------------------------------------------------
-- 2.1 历史推荐统计表 (rucp_history_recommend_stat)
-- --------------------------------------------------------
-- 历史推荐统计表，存储匹配次数统计（由同步服务生成）
CREATE TABLE IF NOT EXISTS rucp_history_recommend_stat (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_cname VARCHAR(200) NOT NULL COMMENT '来源字段中文名',
    source_ename VARCHAR(200) COMMENT '来源字段英文名',
    target_element_code VARCHAR(100) NOT NULL COMMENT '目标数据元代码',
    target_cn_name VARCHAR(200) COMMENT '目标数据元中文名',
    target_en_name VARCHAR(200) COMMENT '目标数据元英文名',
    target_type VARCHAR(50) COMMENT '目标数据类型',
    target_length VARCHAR(50) COMMENT '目标数据长度',
    target_classify VARCHAR(50) COMMENT '目标分类',
    determiner VARCHAR(100) COMMENT '限定词',
    match_count INT DEFAULT 0 COMMENT '匹配次数',
    last_match_time DATETIME COMMENT '最后匹配时间',
    status VARCHAR(2) DEFAULT '1' COMMENT '状态',
    createtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_source_target (source_cname, target_element_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史推荐统计表';

-- --------------------------------------------------------
-- 2.2 同步状态表 (rucp_history_sync_state)
-- --------------------------------------------------------
-- 同步状态表，记录同步进度
CREATE TABLE IF NOT EXISTS rucp_history_sync_state (
    id INT PRIMARY KEY,
    last_sync_id INT DEFAULT 0 COMMENT '上次同步的最大ID',
    last_sync_time DATETIME COMMENT '上次同步时间',
    createtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='同步状态表';

-- ============================================================
-- 3. 可选表结构
-- ============================================================

-- --------------------------------------------------------
-- 3.1 标准数据集表 (rucp_standard_dataset)
-- --------------------------------------------------------
-- 标准数据集表，存储标准表目录
CREATE TABLE IF NOT EXISTS rucp_standard_dataset (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_code VARCHAR(100) NOT NULL COMMENT '表代码',
    table_name VARCHAR(200) NOT NULL COMMENT '表中文名',
    table_ename VARCHAR(200) COMMENT '表英文名',
    table_type VARCHAR(50) COMMENT '表类型',
    status VARCHAR(2) DEFAULT '1' COMMENT '状态',
    createtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_table_code (table_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标准数据集表';

-- --------------------------------------------------------
-- 3.2 标准数据集字段表 (rucp_standard_dataset_field)
-- --------------------------------------------------------
-- 标准数据集字段表，存储标准表字段信息
CREATE TABLE IF NOT EXISTS rucp_standard_dataset_field (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_code VARCHAR(100) NOT NULL COMMENT '表代码',
    field_code VARCHAR(100) NOT NULL COMMENT '字段代码',
    field_name VARCHAR(200) NOT NULL COMMENT '字段中文名',
    field_ename VARCHAR(200) COMMENT '字段英文名',
    field_type VARCHAR(50) COMMENT '字段类型',
    field_length VARCHAR(50) COMMENT '字段长度',
    status VARCHAR(2) DEFAULT '1' COMMENT '状态',
    createtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatetime DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_table_field (table_code, field_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标准数据集字段表';

-- ============================================================
-- 4. 数据库用户和权限
-- ============================================================

-- 创建数据库用户（根据实际情况修改密码）
-- CREATE USER 'metadata'@'%' IDENTIFIED BY 'your_password';
-- CREATE USER 'metadata_history'@'%' IDENTIFIED BY 'your_password';

-- 授权
-- GRANT SELECT, INSERT, UPDATE, DELETE ON metadata.* TO 'metadata'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON metadata_history.* TO 'metadata_history'@'%';
-- FLUSH PRIVILEGES;