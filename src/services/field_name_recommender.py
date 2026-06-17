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

根据提供的字段名称，给出最可能的中文名称。字段名称可能是：
1. 英文，如 user_name, create_time
2. 拼音，如 yonghu_name, chuangjian_shijian
3. 拼音首字母缩写，如 yhm, cjsj

【重要】你必须只输出纯 JSON 格式，不要任何额外内容：
- 不要输出 Markdown 格式（不要 ```json ``` 包裹）
- 不要输出解释说明
- 不要输出分析过程
- 直接输出 JSON 对象

输出 JSON 格式：
{
  "recommendations": [
    {
      "field_name": "原始名称",
      "cn_name": "推荐的中文名",
      "confidence": "高/中/低",
      "reason": "推荐原因"
    }
  ]
}

可信度规则：
- 高：常见的标准字段名，如 id, name, code, type, yhm(用户), cjsj(创建时间)等
- 中：组合词或常见缩写，如 user_name, yonghu_ming等
- 低：不常见或需要更多上下文才能确定的字段"""

        user_prompt = """请为以下 {} 个字段逐个推荐中文名（可能是英文、拼音或拼音首字母缩写）：

{}

【重要】必须为每一个字段都给出推荐结果，不能遗漏任何一个。
输出 JSON 格式的数组，包含所有 {} 个字段的推荐结果。""".format(len(field_names), fields_str, len(field_names))

        try:
            result = self._client.chat_json(
                system=system_prompt,
                user=user_prompt
            )
            logger.info("字段名称推荐完成，共 {} 个字段".format(len(field_names)))
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