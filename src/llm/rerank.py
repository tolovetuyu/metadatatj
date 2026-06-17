"""阶段 3：LLM 精排。"""

from __future__ import annotations

import logging
from typing import Any

from config import settings
from llm.client import LLMClient

logger = logging.getLogger(__name__)

_ELEMENT_RERANK_SYSTEM = """你是公安标准数据元对标专家。根据来源字段，从候选数据元列表中选出最匹配的 Top N。
只能从候选列表中选择，禁止编造 ID。

【重要】你必须只输出纯 JSON 格式，不要任何额外内容：
- 不要输出 Markdown 格式（不要 ```json ``` 包裹）
- 不要输出解释说明
- 直接输出 JSON 对象

输出 JSON 格式：
{
  "rankings": [
    {"element_code": "DE...", "score": 0.95, "reason": "简短理由"}
  ]
}
score 为 0-1，按匹配度降序，数量不超过要求的 N。"""

_QUALIFIER_RERANK_SYSTEM = """你是公安标准限定词对标专家。根据限定词语义，从候选限定词列表中选出 Top N。
只能从候选列表中选择 identifier 字段，禁止编造。

【重要】你必须只输出纯 JSON 格式，不要任何额外内容：
- 不要输出 Markdown 格式（不要 ```json ``` 包裹）
- 不要输出解释说明
- 直接输出 JSON 对象

输出 JSON 格式：
{
  "rankings": [
    {"identifier": "XX", "score": 0.9, "reason": "简短理由"}
  ]
}
score 为 0-1，按匹配度降序。"""


def _fallback_rankings(candidates: list[dict[str, Any]], id_key: str, top_n: int) -> list[dict[str, Any]]:
    seen = set()
    ordered: list[dict[str, Any]] = []
    for c in sorted(candidates, key=lambda x: x.get("score", 0), reverse=True):
        cid = c.get(id_key)
        if cid in seen:
            continue
        seen.add(cid)
        ordered.append({
            id_key: cid,
            "score": float(c.get("score", 0)),
            "reason": "向量召回",
        })
        if len(ordered) >= top_n:
            break
    return ordered


def rerank_elements(
    cname: str,
    ename: str,
    decomp_hint: str,
    candidates: list[dict[str, Any]],
    top_n: int | None = None,
    llm: LLMClient | None = None,
) -> list[dict[str, Any]]:
    top_n = top_n or settings.rerank_top_k
    if not candidates:
        return []
    if not settings.llm_rerank_enabled or len(candidates) <= top_n:
        return _fallback_rankings(candidates, "element_code", top_n)

    cand_lines = []
    for c in candidates[: settings.recall_top_k]:
        cand_lines.append(
            f"- {c['element_code']} | {c['cn_name']} | {c.get('en_name', '')} | 召回分={c.get('score', 0):.4f}"
        )
    user = (
        f"来源字段：{cname} ({ename})\n"
        f"分解提示：{decomp_hint}\n"
        f"请选出 Top {top_n} 数据元。\n"
        f"候选列表：\n" + "\n".join(cand_lines)
    )
    try:
        client = llm or LLMClient()
        data = client.chat_json(_ELEMENT_RERANK_SYSTEM, user)
        rankings = data.get("rankings") or []
        code_map = {c["element_code"]: c for c in candidates}
        result = []
        for item in rankings[:top_n]:
            code = item.get("element_code")
            if code in code_map:
                result.append({
                    "element_code": code,
                    "score": float(item.get("score", code_map[code].get("score", 0))),
                    "reason": item.get("reason", ""),
                })
        if result:
            return result
    except Exception as exc:
        logger.warning("数据元 LLM 精排失败，使用向量分: %s", exc)
    return _fallback_rankings(candidates, "element_code", top_n)


def rerank_qualifiers(
    query: str,
    candidates: list[dict[str, Any]],
    top_n: int | None = None,
    llm: LLMClient | None = None,
) -> list[dict[str, Any]]:
    top_n = top_n or settings.rerank_top_k
    if not candidates:
        return []
    if not query or not settings.llm_rerank_enabled:
        return _fallback_rankings(candidates, "identifier", top_n)

    cand_lines = [
        f"- {c['identifier']} | {c['cn_name']} | 召回分={c.get('score', 0):.4f}"
        for c in candidates[: settings.recall_top_k]
    ]
    user = f"限定词语义：{query}\n请选出 Top {top_n}。\n候选：\n" + "\n".join(cand_lines)
    try:
        client = llm or LLMClient()
        data = client.chat_json(_QUALIFIER_RERANK_SYSTEM, user)
        rankings = data.get("rankings") or []
        id_map = {c["identifier"]: c for c in candidates}
        result = []
        for item in rankings[:top_n]:
            ident = item.get("identifier")
            if ident in id_map:
                result.append({
                    "identifier": ident,
                    "score": float(item.get("score", id_map[ident].get("score", 0))),
                    "reason": item.get("reason", ""),
                })
        if result:
            return result
    except Exception as exc:
        logger.warning("限定词 LLM 精排失败: %s", exc)
    return _fallback_rankings(candidates, "identifier", top_n)
