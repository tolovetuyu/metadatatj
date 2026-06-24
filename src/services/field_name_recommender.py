# -*- coding: utf-8 -*-
"""字段名称推荐服务 - 根据字段英文名推荐中文名。"""

from __future__ import annotations

import logging
from typing import Any

from llm.client import LLMClient

logger = logging.getLogger(__name__)


class FieldNameRecommender:
    """字段名称推荐器 - 使用 LLM 推荐中文名。"""

    def __init__(self) -> None:
        self._client = LLMClient()

    def recommend(self, field_names: list[str]) -> dict[str, Any]:
        """
        根据字段英文名推荐中文名。

        Args:
            field_names: 字段英文名列表，如 ["user_name", "user_age", "create_time"]

        Returns:
            {
                "recommendations": [
                    {
                        "field_name": "user_name",
                        "cn_name": "用户名",
                        "confidence": "高/中/低",
                        "reason": "推荐原因"
                    }
                ]
            }
        """
        if not field_names:
            return {"recommendations": []}

        # 构建字段列表
        field_list = []
        for i, name in enumerate(field_names, 1):
            field_list.append("{}. {}".format(i, name))

        fields_str = "\n".join(field_list)

        system_prompt = """你是一位资深的数据架构师，擅长根据字段英文名或拼音推断其中文含义。

【强制要求】你必须为输入的每一个字段都生成推荐结果！

字段名称可能是：
1. 英文，如 user_name, create_time
2. 拼音，如 yonghu_name, chuangjian_shijian
3. 拼音首字母缩写，如 yhm, cjsj

输出格式示例（包含所有字段）：
{
  "recommendations": [
    {"field_name": "user_name", "cn_name": "用户名", "confidence": "高", "reason": "原因"},
    {"field_name": "user_age", "cn_name": "用户年龄", "confidence": "高", "reason": "原因"},
    {"field_name": "create_time", "cn_name": "创建时间", "confidence": "高", "reason": "原因"}
  ]
}

必须包含全部输入字段！"""

        user_prompt = """请为以下 {} 个字段逐个推荐中文名：

{}

【强制要求】输出包含 "recommendations" 键的 JSON 对象，数组中必须包含全部 {} 个字段！""".format(len(field_names), fields_str, len(field_names))

        try:
            result = self._client.chat_json(
                system=system_prompt,
                user=user_prompt
            )
            logger.info("字段名称推荐完成，共 {} 个字段".format(len(field_names)))
            
            # 检查返回结果
            if isinstance(result, dict) and "recommendations" in result:
                recs = result["recommendations"]
                if len(recs) < len(field_names):
                    logger.warning("LLM 返回字段数不足: 期望 {} 个，实际 {} 个".format(len(field_names), len(recs)))
            return result
        except Exception as e:
            logger.error("字段名称推荐失败: {}".format(e))
            raise RuntimeError("字段名称推荐失败: {}".format(e))


# 全局单例
_recommender: FieldNameRecommender | None = None


def get_field_name_recommender() -> FieldNameRecommender:
    """获取字段名称推荐器单例。"""
    global _recommender
    if _recommender is None:
        _recommender = FieldNameRecommender()
    return _recommender