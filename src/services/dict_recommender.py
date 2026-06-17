# -*- coding: utf-8 -*-
"""字典推荐服务 - 使用向量库匹配推荐字典。"""

from __future__ import annotations

import logging
from typing import Any

from vector.chroma_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class DictRecommender:
    """字典推荐器 - 使用向量库匹配。"""

    def __init__(self, store: ChromaVectorStore) -> None:
        self._store = store

    def recommend(self, enum_values: list[str], top_k: int = 5) -> list[dict[str, Any]]:
        """
        根据枚举值推荐字典。

        Args:
            enum_values: 枚举值列表，如 ["男", "女"]
            top_k: 返回前几个推荐

        Returns:
            [
                {
                    "dict_id": 1,
                    "dict_name": "性别-字典字段(2值)",
                    "dict_code": "CS000001",
                    "match_count": 2,
                    "confidence": "高/中/低",
                    "reason": "枚举值['男', '女'] 全部匹配"
                }
            ]
        """
        if not enum_values:
            return []

        # 查询向量库
        results = self._store.search_dict_items(enum_values, top_k=top_k * 2)

        if not results:
            return []

        # 统计每个字典的匹配情况
        dict_stats = {}
        enum_count = len(enum_values)

        for r in results:
            dict_id = r["dict_id"]
            dict_name = r["dict_name"]
            dict_code = r["dict_code"]
            item_name = r["item_name"]
            score = r.get("score", 0)

            if dict_id not in dict_stats:
                dict_stats[dict_id] = {
                    "dict_id": dict_id,
                    "dict_name": dict_name,
                    "dict_code": dict_code,
                    "match_count": 0,
                    "items": [],
                    "score": 0.0,
                }

            dict_stats[dict_id]["match_count"] += 1
            dict_stats[dict_id]["items"].append(item_name)
            dict_stats[dict_id]["score"] += score

        # 计算可信度并排序
        recommendations = []

        for dict_id, stats in dict_stats.items():
            match_count = stats["match_count"]
            match_rate = match_count / enum_count

            # 可信度计算
            if match_count >= 2 and match_rate >= 0.8:
                confidence = "高"
            elif match_count >= 1 and match_rate >= 0.5:
                confidence = "中"
            else:
                confidence = "低"

            reason = "匹配了 {} 个枚举值: {}".format(
                match_count, ", ".join(stats["items"][:3])
            )

            recommendations.append({
                "dict_id": stats["dict_id"],
                "dict_name": stats["dict_name"],
                "dict_code": stats["dict_code"],
                "match_count": match_count,
                "confidence": confidence,
                "reason": reason,
            })

        # 按匹配数排序，返回前 top_k 个
        recommendations.sort(key=lambda x: x["match_count"], reverse=True)
        return recommendations[:top_k]


# 全局单例
_recommender: DictRecommender | None = None


def get_dict_recommender(store: ChromaVectorStore) -> DictRecommender:
    """获取字典推荐器���例。"""
    global _recommender
    if _recommender is None:
        _recommender = DictRecommender(store)
    return _recommender