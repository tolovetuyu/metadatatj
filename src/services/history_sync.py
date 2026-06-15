"""历史推荐统计同步服务。

支持两种数据源：
1. rucp_task_process 表（position=fast_handle），解析 JSON 提取人工对标结果
2. rucp_element_mapping_history 表，直接读取平铺的历史对标记录

定时从数据源统计匹配次数，更新到统计表。
支持首次全量同步和后续增量同步。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


# 同步状态表名
SYNC_STATE_TABLE = "rucp_history_sync_state"

# 同步状态表中 task_process 同步的行 ID
TASK_PROCESS_SYNC_STATE_ID = 2


class HistorySyncService:
    """历史推荐统计同步服务。"""

    def __init__(self) -> None:
        self._stat_table = settings.history_recommend_table
        # 历史对标记录表（已有的历史对标数据）
        self._history_table = settings.history_source_table
        # 人工对标过程表
        self._task_process_table = settings.task_process_table

    # ------------------------------------------------------------------
    # 同步状态管理
    # ------------------------------------------------------------------

    def _get_last_sync_id(self, state_id: int = 1) -> int:
        """获取上次同步的最大ID。"""
        import db

        try:
            row = db.history_query_one(
                f"SELECT last_sync_id FROM {SYNC_STATE_TABLE} WHERE id = %s",
                (state_id,)
            )
            if row and row.get("last_sync_id"):
                return int(row["last_sync_id"])
        except Exception:
            pass
        return 0

    def _update_last_sync_id(self, sync_id: int, state_id: int = 1) -> None:
        """更新上次同步的最大ID。"""
        import db

        try:
            db.history_execute(
                f"""
                INSERT INTO {SYNC_STATE_TABLE} (id, last_sync_id, last_sync_time, createtime, updatetime)
                VALUES (%s, %s, NOW(), NOW(), NOW())
                ON DUPLICATE KEY UPDATE last_sync_id = %s, last_sync_time = NOW(), updatetime = NOW()
                """,
                (state_id, sync_id, sync_id)
            )
        except Exception as e:
            logger.warning(f"更新同步状态失败: {e}")

    # ------------------------------------------------------------------
    # 数据源 1：rucp_task_process（position=fast_handle）
    # ------------------------------------------------------------------

    @staticmethod
    def _build_determiner(determiner1: str, determiner1_chname: str,
                          determiner2: str, determiner2_chname: str) -> str:
        """构建限定词字符串。

        格式：限定词1中文名/限定词2中文名，仅包含非空部分。
        """
        parts = []
        if determiner1_chname:
            parts.append(determiner1_chname)
        if determiner2_chname:
            parts.append(determiner2_chname)
        return "/".join(parts)

    @staticmethod
    def _extract_field_mappings(content: dict) -> list[dict[str, Any]]:
        """从 task_process 的 JSON content 中提取字段映射关系。

        解析逻辑：
        - input.field 提供 sourceId -> 中文名映射
        - handle.strategy 中 sourceId 非空的条目为人工字段对标结果
        - targetObject 中的 interalEnname/interalChname 为数据元英文/中文名
        - determiner1/determiner2 为限定词信息

        Returns:
            映射记录列表
        """
        # 构建 sourceId -> 中文名映射
        fields = content.get("input", {}).get("field", [])
        source_name_map: dict[str, str] = {}
        for f in fields:
            element_id = f.get("elementid", "") or f.get("aliasname", "")
            ch_name = f.get("chname", "") or f.get("aliasname", "")
            if element_id:
                source_name_map[element_id] = ch_name

        mappings = []
        strategies = content.get("handle", {}).get("strategy", [])
        for strategy in strategies:
            source_id = strategy.get("sourceId", "")
            # 只同步有来源字段的对标结果（跳过系统自动生成的字段）
            if not source_id:
                continue

            target_obj = strategy.get("targetObject", {})
            if not target_obj:
                continue

            source_cname = source_name_map.get(source_id, source_id)
            interal_code = target_obj.get("interalcode", "") or target_obj.get("bzeleid", "")
            determiner1_code = target_obj.get("determiner1", "")
            determiner2_code = target_obj.get("determiner2", "")
            determiner = HistorySyncService._build_determiner(
                determiner1_code,
                target_obj.get("determiner1Chname", ""),
                determiner2_code,
                target_obj.get("determiner2Chname", ""),
            )

            mappings.append({
                "source_cname": source_cname,
                "source_ename": source_id,
                "target_element_code": interal_code,
                "target_cn_name": target_obj.get("interalChname", ""),
                "target_en_name": target_obj.get("interalEnname", ""),
                "target_type": target_obj.get("type", "string"),
                "target_length": int(target_obj.get("length", 0) or 0),
                "target_classify": target_obj.get("classify", ""),
                "determiner": determiner,
                "determiner1_code": determiner1_code,
                "determiner2_code": determiner2_code,
            })

        return mappings

    def sync_from_task_process(self, force_full: bool = False) -> dict[str, Any]:
        """从 rucp_task_process 表同步统计数据。

        同步逻辑：
        1. 读取 position='fast_handle' 的记录
        2. 解析 JSON content，提取字段对标映射
        3. 按 (source_cname, target_element_code) 分组统计匹配次数
        4. 使用 UPSERT 更新统计表

        Args:
            force_full: 是否强制全量同步

        Returns:
            同步结果统计
        """
        import db

        try:
            # 获取上次同步的最大ID
            last_sync_id = 0 if force_full else self._get_last_sync_id(TASK_PROCESS_SYNC_STATE_ID)
            is_full_sync = last_sync_id == 0

            logger.info(
                f"开始从 task_process {'全量' if is_full_sync else '增量'}同步，"
                f"last_sync_id={last_sync_id}"
            )

            # 1. 读取 fast_handle 记录
            rows = db.task_process_query_all(
                f"SELECT id, content FROM {self._task_process_table} "
                f"WHERE position = %s AND id > %s ORDER BY id",
                ("fast_handle", last_sync_id)
            )

            if not rows:
                logger.info("无新增 task_process 记录需要同步")
                return {
                    "status": "success", "synced": 0,
                    "type": "incremental", "last_sync_id": last_sync_id,
                }

            # 2. 解析每条记录的 JSON，提取字段映射
            all_mappings: list[dict[str, Any]] = []
            max_id = 0
            parse_errors = 0

            for row in rows:
                record_id = row["id"]
                max_id = max(max_id, record_id)
                content_str = row.get("content", "")
                if not content_str:
                    continue
                try:
                    content = json.loads(content_str) if isinstance(content_str, str) else content_str
                    mappings = self._extract_field_mappings(content)
                    all_mappings.extend(mappings)
                except (json.JSONDecodeError, TypeError) as e:
                    parse_errors += 1
                    logger.warning(f"解析 task_process id={record_id} 的 JSON 失败: {e}")

            if parse_errors:
                logger.warning(f"共有 {parse_errors} 条记录 JSON 解析失败")

            if not all_mappings:
                logger.info("解析后无有效字段映射")
                self._update_last_sync_id(max_id, TASK_PROCESS_SYNC_STATE_ID)
                return {
                    "status": "success", "synced": 0,
                    "type": "full" if is_full_sync else "incremental",
                    "last_sync_id": max_id, "parse_errors": parse_errors,
                }

            # 3. 按 (source_cname, source_ename, target_element_code, determiner1_code, determiner2_code) 分组统计
            counter: dict[tuple, dict] = {}
            for m in all_mappings:
                key = (
                    m["source_cname"],
                    m["source_ename"],
                    m["target_element_code"],
                    m["determiner1_code"],
                    m["determiner2_code"],
                )
                if key in counter:
                    counter[key]["match_count"] += 1
                else:
                    counter[key] = {
                        "source_cname": m["source_cname"],
                        "source_ename": m["source_ename"],
                        "target_element_code": m["target_element_code"],
                        "target_cn_name": m["target_cn_name"],
                        "target_en_name": m["target_en_name"],
                        "target_type": m["target_type"],
                        "target_length": m["target_length"],
                        "target_classify": m["target_classify"],
                        "determiner": m["determiner"],
                        "determiner1_code": m["determiner1_code"],
                        "determiner2_code": m["determiner2_code"],
                        "match_count": 1,
                    }

            # 4. 使用 UPSERT 更新统计表
            inserted = 0
            for stat in counter.values():
                try:
                    db.history_execute(
                        f"""
                        INSERT INTO {self._stat_table} (
                            source_cname, source_ename, target_element_code,
                            target_cn_name, target_en_name, target_type,
                            target_length, target_classify, determiner,
                            determiner1_code, determiner2_code,
                            match_count, last_match_time, status,
                            createtime, updatetime
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 1, NOW(), NOW())
                        ON DUPLICATE KEY UPDATE
                            match_count = match_count + VALUES(match_count),
                            last_match_time = NOW(),
                            updatetime = NOW()
                        """,
                        (
                            stat["source_cname"],
                            stat["source_ename"],
                            stat["target_element_code"],
                            stat["target_cn_name"],
                            stat["target_en_name"],
                            stat["target_type"],
                            stat["target_length"],
                            stat["target_classify"],
                            stat["determiner"],
                            stat["determiner1_code"],
                            stat["determiner2_code"],
                            stat["match_count"],
                        )
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(f"更新统计记录失败: {e}")

            # 5. 更新同步状态
            self._update_last_sync_id(max_id, TASK_PROCESS_SYNC_STATE_ID)

            sync_type = "full" if is_full_sync else "incremental"
            logger.info(
                f"task_process 同步完成，类型={sync_type}，"
                f"映射={len(all_mappings)}条，去重={inserted}条，"
                f"last_sync_id={max_id}"
            )
            return {
                "status": "success",
                "synced": inserted,
                "type": sync_type,
                "last_sync_id": max_id,
                "total_mappings": len(all_mappings),
                "parse_errors": parse_errors,
            }

        except Exception as e:
            logger.error(f"task_process 同步失败: {e}")
            return {"status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # 数据源 2：rucp_element_mapping_history（原有逻辑）
    # ------------------------------------------------------------------

    def sync_from_history(self, force_full: bool = False) -> dict[str, Any]:
        """从历史对标记录表同步统计数据。

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
            # rucp_element_mapping_history 表无 determiner1_code/determiner2_code 列，使用空串
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
                    '' as determiner1_code,
                    '' as determiner2_code,
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
                            determiner1_code, determiner2_code,
                            match_count, last_match_time, status,
                            createtime, updatetime
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), NOW())
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
                            stat.get("determiner1_code", ""),
                            stat.get("determiner2_code", ""),
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
