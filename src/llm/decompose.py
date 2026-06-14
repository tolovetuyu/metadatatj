"""阶段 1：字段分解。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from config import settings
from llm.client import LLMClient

logger = logging.getLogger(__name__)

_DECOMPOSE_SYSTEM = """你是公安/metadata 数据元对标专家。分析来源字段是否由「限定词 + 数据元」构成。
限定词表示修饰关系（如：父亲、法定代表人、RUN）。
数据元表示核心语义（如：姓名、地址、日期、代码）。
只输出 JSON，字段：
- core_element_hint: 数据元核心语义（字符串）
- qualifier_hints: 限定词列表（字符串数组，可为空）
- english_hint: 英文名语义提示
- confidence: 0-1 浮点数
"""

_SUFFIXES = ("姓名", "地址", "日期", "时间", "代码", "编号", "金额", "状况", "情况", "名称")


@dataclass
class FieldDecomposition:
    core_element_hint: str
    qualifier_hints: list[str] = field(default_factory=list)
    english_hint: str = ""
    confidence: float = 0.5
    raw_determiners: list[str] = field(default_factory=list)


def _rule_decompose(cname: str, ename: str) -> FieldDecomposition:
    text = cname.strip()
    qualifier_hints: list[str] = []
    core = text

    for suffix in _SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            core = suffix
            prefix = text[: -len(suffix)]
            if prefix:
                qualifier_hints.append(prefix)
            break

    if text.startswith("是否"):
        core = "状态代码"
        qualifier_hints = [text]

    return FieldDecomposition(
        core_element_hint=core,
        qualifier_hints=qualifier_hints,
        english_hint=ename,
        confidence=0.6,
        raw_determiners=qualifier_hints.copy(),
    )


def decompose_field(cname: str, ename: str, llm: LLMClient | None = None) -> FieldDecomposition:
    if not settings.llm_decompose_enabled:
        return _rule_decompose(cname, ename)

    try:
        client = llm or LLMClient()
        user = f"来源字段中文：{cname}\n来源字段英文：{ename}"
        data: dict[str, Any] = client.chat_json(_DECOMPOSE_SYSTEM, user)
        hints = data.get("qualifier_hints") or []
        if isinstance(hints, str):
            hints = [hints] if hints else []
        return FieldDecomposition(
            core_element_hint=str(data.get("core_element_hint") or cname).strip(),
            qualifier_hints=[str(h).strip() for h in hints if str(h).strip()],
            english_hint=str(data.get("english_hint") or ename).strip(),
            confidence=float(data.get("confidence") or 0.8),
            raw_determiners=[str(h).strip() for h in hints if str(h).strip()],
        )
    except Exception as exc:
        logger.warning("LLM 分解失败，使用规则兜底: %s", exc)
        return _rule_decompose(cname, ename)


def build_retrieval_queries(cname: str, ename: str, decomp: FieldDecomposition) -> dict[str, list[str]]:
    element_queries = list(dict.fromkeys([
        cname,
        f"{decomp.core_element_hint} {decomp.english_hint}".strip(),
        decomp.core_element_hint,
    ]))
    qualifier_queries: list[str] = []
    for q in decomp.qualifier_hints:
        qualifier_queries.append(q)
    if not qualifier_queries and decomp.raw_determiners:
        qualifier_queries.extend(decomp.raw_determiners)
    qualifier_queries = list(dict.fromkeys([q for q in qualifier_queries if q]))
    return {"element": element_queries, "qualifier": qualifier_queries}


def normalize_det_queries(decomp: FieldDecomposition, use_human_det: bool) -> list[str]:
    """与 quick 一致的限定词检索串策略。"""
    if use_human_det:
        return ["".join(decomp.raw_determiners)] if decomp.raw_determiners else []
    dets = decomp.raw_determiners
    if len(dets) < 3:
        return [d for d in dets if d]
    return ["".join(dets[:-1]), dets[-1]]
