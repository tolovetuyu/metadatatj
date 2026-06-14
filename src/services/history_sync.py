"""历史推荐统计同步服务。

定时从历史对标记录表统计匹配次数，更新到统计表。
支持首次全量同步和后续增量同步。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


# 同步状态表名
SYNC_STATE_TABLE = "rucp_history_sync_state"


class HistorySyncService:
    """历史推荐统计同步服务。"""

    def __init__(self) -> None:
        self._stat_table = settings.history_recommend_table
        # 历史对标记录表（已有的历史对标数据）
        self._history_table = settings.history_source_table

    def _get_last_sync_id(self) -> int:
        """获取上次同步的最大ID。"""
        import db

        try:
            row = db.history_query_one(
                f"SELECT last_sync_id FROM {SYNC_STATE_TABLE} WHERE id = 1"
            )
            if row and row.get("last_sync_id"):
                return int(row["last_sync_id"])
        except Exception:
            pass
        return 0

    def _update_last_sync_id(self, sync_id: int) -> None:
        """更新上次同步的最大ID。"""
        import db

        try:
            db.history_execute(
                f"""
                INSERT INTO {SYNC_STATE_TABLE} (id, last_sync_id, last_sync_time, createtime, updatetime)
                VALUES (1, %s, NOW(), NOW(), NOW())
                ON DUPLICATE KEY UPDATE last_sync_id = %s, last_sync_time = NOW(), updatetime = NOW()
                """,
                (sync_id, sync_id)
            )
        except Exception as e:
            logger.warning(f"更新同步状态失败: {e}")

    def sync_from_history(self, force_full: bool = False) -> dict[str, Any]:
        """
        从历史对标记录表同步统计数据。
        
        同步逻辑：
        1. 首次或 force_full=True 时全量同步
        2. 后续根据 id 增量同步
        3. 统计每个来源字段对应各数据元的匹配次数
        4. 使用 UPSERT 更新统计表
        
        Args:
            force_full: 是否强制全量同步
            
        Returns:
            同步结果统计
        """
        import db

        try:
            # 获取上次同步的最大ID
            last_sync_id = 0 if force_full else self._get_last_sync_id()
            is_full_sync = last_sync_id == 0

            logger.info(f"开始{'全量' if is_full_sync else '增量'}同步，last_sync_id={last_sync_id}")

            # 1. 统计历史对标记录（id > last_sync_id）
            # 按 (source_cname, target_element_code) 分组统计匹配次数
            stats = db.history_query_all(f"""
                SELECT 
                    source_cname,
                    source_ename,
                    target_element_code,
                    target_cn_name,
                    target_en_name,
                    target_type,
                    target_length,
                    target_classify,
                    determiner,
                    COUNT(*) as match_count,
                    MAX(update_time) as last_match_time,
                    MAX(id) as max_id
                FROM {self._history_table}
                WHERE id > %s AND status = 1
                GROUP BY source_cname, source_ename, target_element_code
            """, (last_sync_id,))

            if not stats:
                logger.info("无新增历史记录需要同步")
                return {"status": "success", "synced": 0, "type": "incremental", "last_sync_id": last_sync_id}

            # 2. 获取本次同步的最大ID
            max_id = max(s.get("max_id", 0) or 0 for s in stats)

            # 3. 使用 UPSERT 更新统计表（存在则累加，不存在则插入）
            inserted, updated = 0, 0
            for stat in stats:
                try:
                    result = db.history_execute(
                        f"""
                        INSERT INTO {self._stat_table} (
                            source_cname, source_ename, target_element_code,
                            target_cn_name, target_en_name, target_type,
                            target_length, target_classify, determiner,
                            match_count, last_match_time, status,
                            createtime, updatetime
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), NOW())
                        ON DUPLICATE KEY UPDATE 
                            match_count = match_count + VALUES(match_count),
                            last_match_time = VALUES(last_match_time),
                            updatetime = NOW()
                        """,
                        (
                            stat["source_cname"],
                            stat.get("source_ename", ""),
                            stat["target_element_code"],
                            stat.get("target_cn_name", ""),
                            stat.get("target_en_name", ""),
                            stat.get("target_type", "string"),
                            stat.get("target_length", 0),
                            stat.get("target_classify", ""),
                            stat.get("determiner", ""),
                            stat["match_count"],
                            stat["last_match_time"],
                        )
                    )
                    if result > 0:
                        inserted += 1
                except Exception as e:
                    logger.warning(f"更新统计记录失败: {e}")

            # 4. 更新同步状态
            self._update_last_sync_id(max_id)

            sync_type = "full" if is_full_sync else "incremental"
            logger.info(f"同步完成，类型={sync_type}，处理={inserted}条，last_sync_id={max_id}")
            return {
                "status": "success",
                "synced": inserted,
                "type": sync_type,
                "last_sync_id": max_id,
            }

        except Exception as e:
            logger.error(f"同步失败: {e}")
            return {"status": "error", "message": str(e)}


# 全局同步服务实例
_sync_service: HistorySyncService | None = None


def get_sync_service() -> HistorySyncService:
    """获取同步服务单例。"""
    global _sync_service
    if _sync_service is None:
        _sync_service = HistorySyncService()
    return _sync_service
