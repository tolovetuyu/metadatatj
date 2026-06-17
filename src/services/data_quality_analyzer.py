# -*- coding: utf-8 -*-
"""数据质量分析服务 - 调用 LLM 提供数据治理建议。"""

from __future__ import annotations

import logging
from typing import Any

from llm.client import LLMClient

logger = logging.getLogger(__name__)


class DataQualityAnalyzer:
    """数据质量分析器 - 调用 LLM 提供治理建议。"""

    # 字段映射：Java 字段名 -> 数据库字段名
    FIELD_MAP = {
        "enname": "enname",
        "chname": "chname",
        "length": "length",
        "type": "type",
        "mostAppear": "most_appear",
        "maxSize": "max_size",
        "minSize": "min_size",
        "sampleCount": "sample_count",
        "fillRate": "fill_rate",
        "fieldLen": "field_len",
        "dataLenMax": "data_len_max",
        "dataLenMin": "data_len_min",
        "dataLenMid": "data_len_mid",
        "dataLenMode": "data_len_mode",
        "dataLenExcept": "data_len_excpt",
        "dataLenRate": "data_len_rate",
        "fieldType": "field_type",
        "sampleType": "sample_type",
        "dataTypeRate": "data_type_rate",
        "dataTypeExcept": "data_type_except",
        "numberMax": "number_max",
        "numberMin": "number_min",
        "numberMid": "number_mid",
        "numberMode": "number_mode",
        "numberUniqCount": "number_uniq_count",
        "numberUniqValues": "number_uniq_values",
        "unionDict": "union_dict",
        "dictRate": "dict_rate",
        "dictExcept": "dict_except",
        "entityType": "entity_type",
        "entityRate": "entity_rate",
        "entityExcept": "entity_except",
        "entityNormalizeRate": "entity_normalize_rate",
        "dictCount": "dict_count",
        "dictExceptCount": "dict_except_count",
        "dataFormatRate": "data_format_rate",
        "requiredFillRate": "required_fill_rate",
        "averageValue": "average_value",
        "maxValue": "max_value",
        "minValue": "min_value",
    }

    def __init__(self) -> None:
        self._client = LLMClient()

    def analyze(self, dataset_name: str, fields_info: list[dict[str, Any]]) -> dict[str, Any]:
        """分析数据质量并提供治理建议。"""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(dataset_name, fields_info)

        logger.info(f"正在分析数据集: {dataset_name}, 字段数: {len(fields_info)}")

        try:
            result = self._client.chat_text(
                system=system_prompt,
                user=user_prompt
            )
            logger.info("LLM 分析完成")
            return {
                "dataset_name": dataset_name,
                "field_count": len(fields_info),
                "recommendations": result
            }
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            raise RuntimeError(f"LLM 分析失败: {e}")

    def _build_system_prompt(self) -> str:
        """构建系统提示词。"""
        return """你是一位资深的数据治理专家。分析数据质量问题并提供实用的治理建议。

【重要】直接输出结果，不要输出分析过程或思考过程。输出紧凑格式，不要有多余空行。

输出必须是纯文本（不是 JSON），简洁易读。重点关注：
1. 每个字段存在的问题（空值、格式异常、类型不匹配等）和整改建议
2. **仅对可能是字典的字段**（如性别、民族、学历、婚姻状况等枚举型字段）推荐字典
3. 对于明显不是字典的字段（如姓名、地址、电话、日期等自由文本字段）不要提及字典

输出格式（紧凑，无多余空行）：
## 字段分析
[字段名]: [问题列表] -> [建议]
## 字典推荐（仅针对枚举型字段）
[字段名]: 建议使用[字典名]字典，可信度:[高/中/低]，原因:[原因]
## 优先处理
1. [事项1]
2. [事项2]
## 整体总结
[一句话总结]"""

    def _build_user_prompt(self, dataset_name: str, fields_info: list[dict[str, Any]]) -> str:
        """构建用户提示词。"""
        # 所有质量相关字段名（Java 格式）
        quality_fields = [
            "length", "type",
            "mostAppear", "maxSize", "minSize", "sampleCount", "fillRate",
            "fieldLen", "dataLenMax", "dataLenMin", "dataLenMid", "dataLenMode", "dataLenExcept", "dataLenRate",
            "fieldType", "sampleType", "dataTypeRate", "dataTypeExcept",
            "numberMax", "numberMin", "numberMid", "numberMode", "numberUniqCount", "numberUniqValues",
            "unionDict", "dictRate", "dictExcept",
            "entityType", "entityRate", "entityExcept", "entityNormalizeRate",
            "dictCount", "dictExceptCount", "dataFormatRate", "requiredFillRate",
            "averageValue", "maxValue", "minValue"
        ]
        
        field_lines = []
        for field in fields_info:
            field_name = field.get("enname", field.get("chname", "Unknown"))
            chname = field.get("chname", field_name)
            
            # 构建包含所有质量指标的行
            parts = [f"{field_name}({chname})"]
            
            for qf in quality_fields:
                if qf in field and field[qf]:
                    val = field[qf]
                    # 缩短过长的值
                    if isinstance(val, str) and len(val) > 30:
                        val = val[:30] + "..."
                    parts.append(f"{qf}:{val}")
            
            field_lines.append(", ".join(parts))

        prompt = f"""分析数据集 '{dataset_name}' 的字段质量，共 {len(fields_info)} 个字段。

字段质量信息:
{chr(10).join(field_lines)}

请给出紧凑格式的结果（无多余空行）：
1. 每个字段存在的问题和整改建议
2. **仅对枚举型字段**（如性别、民族、学历等固定值域字段）推荐字典及可信度
3. 对于自由文本字段（如姓名、地址、电话等）不要提及字典
4. 优先处理的事项
5. 一句话整体总结"""

        return prompt


# 全局单例
_analyzer: DataQualityAnalyzer | None = None


def get_data_quality_analyzer() -> DataQualityAnalyzer:
    """获取数据质量分析器单例。"""
    global _analyzer
    if _analyzer is None:
        _analyzer = DataQualityAnalyzer()
    return _analyzer