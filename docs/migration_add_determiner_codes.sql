-- ============================================================
-- 迁移脚本：为 rucp_history_recommend_stat 添加限定词编码字段
-- 日期: 2026-06-11
-- ============================================================

-- 1. 添加限定词编码字段
ALTER TABLE rucp_history_recommend_stat
  ADD COLUMN determiner1_code VARCHAR(64) DEFAULT '' COMMENT '限定词1编码（如 RYBH、RUN）',
  ADD COLUMN determiner2_code VARCHAR(64) DEFAULT '' COMMENT '限定词2编码（如 CJD、GLHT）';

-- 2. 更新唯一键，纳入限定词编码
-- 同一来源+数据元可能对应不同限定词组合，需区分存储
-- 先查看当前唯一键名: SHOW CREATE TABLE rucp_history_recommend_stat;
-- 然后替换下面的旧键名（如 uk_source_target）
ALTER TABLE rucp_history_recommend_stat DROP INDEX uk_source_target;
ALTER TABLE rucp_history_recommend_stat ADD UNIQUE KEY uk_source_target_det
  (source_cname, source_ename, target_element_code, determiner1_code, determiner2_code);
