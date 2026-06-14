"""历史推荐结果服务，优先使用人工推荐的历史记录。

使用内存缓存 + 数据库存储：
- 启动时从数据库加载到内存缓存
- 定时任务更新缓存
- 查询直接从缓存读取，无IO开销
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class HistoryRecommend:
    """历史推荐记录。"""
    source_cname: str
    source_ename: str
    target_element_code: str
    target_cn_name: str
    target_en_name: str
    target_type: str
    target_length: int
    target_classify: str
    match_count: int  # 匹配次数
    determiner: str = ""


class HistoryRecommender:
    """历史推荐结果查询服务（内存缓存模式）。"""

    def __init__(self) -> None:
        self._enabled = settings.history_recommend_enabled
        self._table_name = settings.history_recommend_table
        # 内存缓存: key=source_cname, value=List[HistoryRecommend]
        self._cache: dict[str, list[HistoryRecommend]] = {}
        self._cache_lock = threading.RLock()
        # 是否已加载缓存
        self._loaded = False

    def load_cache(self) -> int:
        """
        从数据库加载历史推荐统计到内存缓存。
        应用启动时调用，或定时任务调用以刷新缓存。
        """
        if not self._enabled:
            logger.info("历史推荐未启用，跳过缓存加载")
            return 0

        import db

        try:
            # 查询所有历史推荐统计，按匹配次数降序（使用历史数据库）
            rows = db.history_query_all(f"""
                SELECT 
                    source_cname, source_ename, target_element_code,
                    target_cn_name, target_en_name, target_type,
                    target_length, target_classify, determiner, match_count
                FROM {self._table_name}
                WHERE status = 1
                ORDER BY source_cname, match_count DESC
            """)

            # 构建缓存
            new_cache: dict[str, list[HistoryRecommend]] = {}
            for row in rows:
                source_cname = row["source_cname"]
                if source_cname not in new_cache:
                    new_cache[source_cname] = []
                new_cache[source_cname].append(HistoryRecommend(
                    source_cname=source_cname,
                    source_ename=row.get("source_ename", ""),
                    target_element_code=row["target_element_code"],
                    target_cn_name=row.get("target_cn_name", ""),
                    target_en_name=row.get("target_en_name", ""),
                    target_type=row.get("target_type", "string"),
                    target_length=int(row.get("target_length", 0) or 0),
                    target_classify=row.get("target_classify", ""),
                    match_count=int(row.get("match_count", 1) or 1),
                    determiner=row.get("determiner", ""),
                ))

            # 原子更新缓存
            with self._cache_lock:
                self._cache = new_cache
                self._loaded = True

            logger.info(f"历史推荐缓存加载完成，共 {len(rows)} 条记录，{len(new_cache)} 个源字段")
            return len(rows)

        except Exception as e:
            logger.error(f"加载历史推荐缓存失败: {e}")
            return 0

    def get_history(self, source_cname: str, source_ename: str = "") -> list[HistoryRecommend]:
        """获取历史推荐记录（从缓存读取）。"""
        if not self._enabled:
            return []

        with self._cache_lock:
            # 优先用 source_cname 查找
            if source_cname in self._cache:
                return self._cache[source_cname]
            # 备选用 source_ename 查找
            if source_ename and source_ename in self._cache:
                return self._cache[source_ename]
        return []

    def merge_with_candidates(
        self,
        source_cname: str,
        source_ename: str,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        将历史推荐结果与候选结果合并。
        
        历史结果（按匹配次数排序）优先排在前面，
        剩余位置由模型/向量库候选结果补充。
        """
        if not self._enabled:
            return candidates[:top_k]

        history = self.get_history(source_cname, source_ename)
        if not history:
            return candidates[:top_k]

        # 将历史结果转换为候选格式
        history_candidates = []
        for h in history:
            history_candidates.append({
                "element_code": h.target_element_code,
                "cn_name": h.target_cn_name,
                "en_name": h.target_en_name,
                "type": h.target_type,
                "length": h.target_length,
                "classify": h.target_classify,
                "score": 1.0,  # 历史结果给最高分
                "is_history": True,
                "match_count": h.match_count,
                "determiner": h.determiner,
            })

        # 合并结果：历史结果在前，去重后的候选结果在后
        used_codes = {h.target_element_code for h in history}
        remaining_candidates = [c for c in candidates if c.get("element_code") not in used_codes]

        # 计算需要从候选中取的数量
        history_count = min(len(history_candidates), top_k)
        remaining_count = top_k - history_count

        merged = history_candidates[:history_count] + remaining_candidates[:remaining_count]
        return merged

    def is_loaded(self) -> bool:
        """检查缓存是否已加载。"""
        with self._cache_lock:
            return self._loaded

    def get_cache_stats(self) -> dict[str, int]:
        """获取缓存统计信息。"""
        with self._cache_lock:
            total_records = sum(len(v) for v in self._cache.values())
            return {
                "source_count": len(self._cache),
                "total_records": total_records,
                "loaded": self._loaded,
            }


# 全局单例
_recommender: HistoryRecommender | None = None


def get_history_recommender() -> HistoryRecommender:
    """获取历史推荐服务单例。"""
    global _recommender
    if _recommender is None:
        _recommender = HistoryRecommender()
    return _recommender
