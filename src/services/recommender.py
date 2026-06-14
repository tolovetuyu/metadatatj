"""数据元/限定词推荐核心服务（三阶段流水线）。"""

from __future__ import annotations

import logging
from typing import Any

from config import settings
from knowledge_loader import KnowledgeBase
from llm.client import LLMClient
from llm.decompose import (
    FieldDecomposition,
    build_retrieval_queries,
    decompose_field,
    normalize_det_queries,
)
from llm.rerank import rerank_elements, rerank_qualifiers
from rules.dict_rules import GYH_MAP, ZK_CODES, extend_field, get_dict_fields, get_dict_mapinfo
from services.history_recommender import get_history_recommender
from vector.chroma_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class MetadataRecommender:
    def __init__(
        self,
        kb: KnowledgeBase,
        store: ChromaVectorStore | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.kb = kb
        self.store = store or ChromaVectorStore()
        self.llm = llm or LLMClient()
        self._element_by_code = kb.element_items.set_index("element_code").to_dict("index")
        self._history = get_history_recommender()

    def _resolve_element_row(self, cn_name: str, meta: dict[str, Any]) -> tuple:
        """构建数据元返回行。"""
        return (
            meta.get("cn_name", cn_name),
            meta.get("en_name", ""),
            meta.get("type", "string"),
            int(meta.get("length", 0) or 0),
            meta.get("classify", ""),
            meta.get("element_code", ""),
            "",
        )

    def _apply_photo_rule(self, top_cn: str, element_query: str) -> str:
        """照片特殊规则：照片 → 电子文件存放路径。"""
        if top_cn == "照片":
            return "电子文件存放路径"
        return element_query

    def _build_gz(self, cname: str, ename: str, element_cnames: list[str], not_dict: bool, gz_seed: list) -> list[str]:
        gz: list[str] = list(gz_seed) if gz_seed else []
        if not not_dict:
            return gz
        while len(gz) < len(element_cnames):
            gz.append("")
        for i, element_cname in enumerate(element_cnames):
            if gz[i]:
                continue
            tpl = self.kb.gz_map.get(element_cname, "")
            if not tpl:
                continue
            fmt = "yyyyMMdd" if (element_cname.endswith("日期") or cname.endswith("日期")) else "yyyyMMddHHmmss"
            gz[i] = tpl.format(ename, fmt)
        return gz[: len(element_cnames)]

    def recommend(
        self,
        cname: str,
        ename: str,
        source_type: str = "string",
        length: int = 4000,
        gz: list | None = None,
        map_list: list | None = None,
        not_dict: bool = True,
        extend_label: bool = False,
        extend_key: str = "",
    ) -> dict[str, Any]:
        gz = gz or []
        map_list = map_list or []

        decomp = decompose_field(cname, ename, self.llm)
        if (not extend_label) and decomp.core_element_hint in ZK_CODES:
            decomp = decompose_field(cname + "代码", ename, self.llm)
        if extend_label and (not decomp.core_element_hint.endswith("代码")):
            decomp.raw_determiners.append(decomp.core_element_hint)
            decomp.core_element_hint = "信息代码"

        queries = build_retrieval_queries(cname, ename, decomp)
        element_query = self._apply_photo_rule(decomp.core_element_hint, decomp.core_element_hint)
        if element_query != decomp.core_element_hint:
            queries["element"].insert(0, element_query)

        raw_candidates = self.store.search_elements(queries["element"], settings.recall_top_k)
        candidates = []
        for c in raw_candidates:
            code = c.get("element_code") or c.get("id")
            if not code:
                continue
            row = self._element_by_code.get(code, {})
            candidates.append({
                "element_code": code,
                "cn_name": c.get("cn_name") or row.get("cn_name", ""),
                "en_name": c.get("en_name") or row.get("en_name", ""),
                "type": c.get("type") or row.get("type", source_type),
                "length": c.get("length") or row.get("length", length),
                "classify": c.get("classify") or row.get("classify", ""),
                "score": c.get("score", 0),
            })

        # 合并历史推荐结果（历史结果优先）
        candidates = self._history.merge_with_candidates(
            cname, ename, candidates, top_k=settings.recall_top_k
        )

        rankings = rerank_elements(
            cname, ename, decomp.core_element_hint, candidates, settings.rerank_top_k, self.llm
        )

        element_cnames, element_enames, element_types = [], [], []
        element_lengths, element_classifys, element_codes, element_scores = [], [], [], []
        determiners_from_hc: list[str] = []

        for rank in rankings:
            code = rank["element_code"]
            meta = self.store.get_element_by_code(code) or {}
            row = self._resolve_element_row(meta.get("cn_name", ""), meta)
            element_cnames.append(row[0])
            element_enames.append(row[1])
            element_types.append(row[2] or source_type)
            element_lengths.append(row[3] or length)
            element_classifys.append(row[4])
            element_codes.append(row[5] or code)
            element_scores.append(rank.get("score", 0))
            if row[6]:
                determiners_from_hc.append(row[6])

        deteminer_label = bool(determiners_from_hc and determiners_from_hc[0])
        deteminers = determiners_from_hc if deteminer_label else []
        deteminer_enames: list[str] = []

        gyh = [GYH_MAP.get(item, "").format(ename) if GYH_MAP.get(item) else "" for item in element_cnames]
        gz_out = self._build_gz(cname, ename, element_cnames, not_dict, gz)

        res: dict[str, Any] = {
            "element": {
                "cname": element_cnames,
                "ename": element_enames,
                "type": element_types,
                "length": element_lengths,
                "classify": element_classifys,
                "elementCode": element_codes,
                "score": element_scores,
                "gz": gz_out,
                "gyh": gyh,
                "mapList": map_list,
                "deteminer": deteminers,
                "deteminerEname": deteminer_enames,
            }
        }
        if extend_label:
            res["extendKey"] = extend_key

        det_queries = normalize_det_queries(decomp, deteminer_label)
        if det_queries:
            det_cnames, det_enames, det_labels, det_scores = [], [], [], []
            for det_q in det_queries:
                q_candidates_raw = self.store.search_qualifiers([det_q], settings.recall_top_k)
                q_candidates = [
                    {
                        "identifier": c.get("identifier") or c.get("id"),
                        "cn_name": c.get("cn_name", ""),
                        "score": c.get("score", 0),
                    }
                    for c in q_candidates_raw
                ]
                q_rank = rerank_qualifiers(det_q, q_candidates, settings.rerank_top_k, self.llm)
                names = []
                for r in q_rank:
                    meta = self.store.get_qualifier_by_id(r["identifier"])
                    names.append(meta["cn_name"] if meta else r["identifier"])
                det_cnames.append(names)
                det_enames.append([r["identifier"] for r in q_rank])
                det_labels.append([0] * len(q_rank))
                det_scores.append([r.get("score", 0) for r in q_rank])
            res["deteminer"] = {
                "cname": det_cnames,
                "ename": det_enames,
                "label": det_labels,
                "score": det_scores,
            }

        return res

    def recommend_batch(self, fields_info: list[dict], lyb_ename: str = "", with_extend: bool = False) -> dict:
        dict_fields = get_dict_fields(self.kb, lyb_ename.upper()).get("dictFields", []) if with_extend else []
        cnames = [f.get("cname", "") for f in fields_info]
        recommend_infos = []
        extend_infos = {}

        for field in fields_info:
            ename = field.get("ename", "")
            cname = field.get("cname", "")
            source_type = field.get("type", "string")
            length = field.get("length", 4000)

            if with_extend and ename.upper() in dict_fields:
                dm = get_dict_mapinfo(self.kb, ename, lyb_ename)
                ext = extend_field(cname, ename)
                (cname1, ename1), (cname2, ename2) = ext[0], ext[1]
                recommend_infos.append(
                    self.recommend(
                        cname1, ename1, source_type, length,
                        [dm.get("func_origin", "")] * settings.rerank_top_k,
                        dm.get("mapList_origin", []),
                        not_dict=False,
                        extend_label=cname2 not in cnames,
                        extend_key=ename2,
                    )
                )
                if cname2 not in cnames:
                    extend_infos[ename2] = self.recommend(
                        cname2, ename2, source_type, length,
                        [dm.get("func", "")] * settings.rerank_top_k,
                        dm.get("mapList", []),
                        not_dict=False,
                    )
            else:
                recommend_infos.append(
                    self.recommend(cname, ename, source_type, length, [], [])
                )

        result = {"recommendInfos": recommend_infos}
        if with_extend:
            result["extendInfos"] = extend_infos
        return result
