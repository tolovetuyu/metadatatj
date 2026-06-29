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
        # 返回 meta 中的 code 字段（数据库的 code 列），而不是中文拼音
        return (
            meta.get("cn_name", cn_name),
            meta.get("code", ""),
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

        logger.info(f"[推荐开始] 字段: {cname} ({ename}), 类型: {source_type}, 长度: {length}")

        # 1. 字段分解
        decomp = decompose_field(cname, ename, self.llm)
        logger.info(
            f"[字段分解] 方式: {'LLM' if settings.llm_decompose_enabled else '规则'}, "
            f"核心数据元: {decomp.core_element_hint}, 限定词: {decomp.raw_determiners}, "
            f"置信度: {decomp.confidence}"
        )

        if (not extend_label) and decomp.core_element_hint in ZK_CODES:
            decomp = decompose_field(cname + "代码", ename, self.llm)
            logger.info(f"[字段分解] 特殊规则触发，重新分解: {cname}代码 → {decomp.core_element_hint}")
        if extend_label and (not decomp.core_element_hint.endswith("代码")):
            decomp.raw_determiners.append(decomp.core_element_hint)
            decomp.core_element_hint = "信息代码"
            logger.info(f"[字段分解] 扩展模式，数据元改为: 信息代码")

        queries = build_retrieval_queries(cname, ename, decomp)
        element_query = self._apply_photo_rule(decomp.core_element_hint, decomp.core_element_hint)
        if element_query != decomp.core_element_hint:
            queries["element"].insert(0, element_query)
            logger.info(f"[特殊规则] 照片 → 电子文件存放路径")

        # 2. 向量召回候选
        raw_candidates = self.store.search_elements(queries["element"], settings.recall_top_k)
        logger.info(
            f"[向量召回] 查询词: {queries['element'][:3]}, "
            f"召回候选数: {len(raw_candidates)}, "
            f"向量库状态: {'有数据' if raw_candidates else '无数据/空'}"
        )
        candidates = []
        for c in raw_candidates:
            code = c.get("element_code") or c.get("id")
            if not code:
                continue
            row = self._element_by_code.get(code, {})
            # 使用数据库的 code 字段（如 XM），而不是中文拼音
            candidates.append({
                "element_code": code,
                "cn_name": c.get("cn_name") or row.get("cn_name", ""),
                "en_name": c.get("code") or row.get("element_code", ""),  # ← 修复：使用 element_code
                "type": c.get("type") or row.get("type", source_type),
                "length": c.get("length") or row.get("length", length),
                "classify": c.get("classify") or row.get("classify", ""),
                "score": c.get("score", 0),
            })

        # 3. 合并历史推荐结果
        candidates = self._history.merge_with_candidates(
            cname, ename, candidates, top_k=settings.recall_top_k
        )
        history_count = sum(1 for c in candidates if c.get("is_history"))
        vector_count = len(candidates) - history_count
        logger.info(
            f"[历史推荐] 启用: {self._history._enabled}, "
            f"历史候选数: {history_count}, 向量候选数: {vector_count}, "
            f"Top1来源: {'历史' if candidates and candidates[0].get('is_history') else '向量'}"
        )

        # 提取历史候选中的限定词编码和元素详情，用于后续直接复用
        history_det_map: dict[str, dict[str, str]] = {}
        history_detail_map: dict[str, dict[str, Any]] = {}
        for c in candidates:
            if c.get("is_history"):
                det1 = c.get("determiner1_code", "")
                det2 = c.get("determiner2_code", "")
                if det1 or det2:
                    history_det_map[c["element_code"]] = {
                        "determiner1_code": det1,
                        "determiner2_code": det2,
                    }
                history_detail_map[c["element_code"]] = {
                    "cn_name": c.get("cn_name", ""),
                    "en_name": c.get("en_name", ""),  # ← 修复：使用历史候选的 en_name 字段（拼音）
                    "type": c.get("type", "string"),
                    "length": c.get("length", 0),
                    "classify": c.get("classify", ""),
                    "element_code": c.get("element_code", ""),
                }

        # 4. LLM 重排序
        rankings = rerank_elements(
            cname, ename, decomp.core_element_hint, candidates, settings.rerank_top_k, self.llm
        )
        logger.info(
            f"[LLM重排序] 启用: {settings.llm_rerank_enabled}, "
            f"输入候选数: {len(candidates)}, 输出结果数: {len(rankings)}, "
            f"Top3: {[r.get('element_code', '') for r in rankings[:3]]}"
        )

        element_cnames, element_enames, element_types = [], [], []
        element_lengths, element_classifys, element_codes, element_scores = [], [], [], []
        determiners_from_hc: list[str] = []

        for rank in rankings:
            code = rank["element_code"]
            meta = self.store.get_element_by_code(code) or {}
            # 添加诊断日志：输出向量库返回的完整 metadata
            logger.info(f"[诊断] element_code={code}, meta keys={list(meta.keys())}, meta.code={meta.get('code')}, meta.element_code={meta.get('element_code')}")
            # 优先用 ChromaDB 数据，ChromaDB 无数据时回退到历史候选详情
            if not meta.get("cn_name") and code in history_detail_map:
                detail = history_detail_map[code]
                element_cnames.append(detail["cn_name"])
                # 从向量库获取 code 字段，而不是历史数据库中的 target_en_name（可能是拼音）
                element_enames.append(meta.get("code", detail.get("en_name", "")))
                element_types.append(detail["type"] or source_type)
                element_lengths.append(detail["length"] or length)
                element_classifys.append(detail["classify"])
                element_codes.append(detail["element_code"] or code)
            else:
                row = self._resolve_element_row(meta.get("cn_name", ""), meta)
                element_cnames.append(row[0])
                element_enames.append(row[1])
                element_types.append(row[2] or source_type)
                element_lengths.append(row[3] or length)
                element_classifys.append(row[4])
                element_codes.append(row[5] or code)
            element_scores.append(rank.get("score", 0))

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

        # 5. 限定词推荐
        history_det = self._find_history_determiners(rankings, history_det_map)
        if history_det:
            res["deteminer"] = self._build_history_deteminer(history_det)
            logger.info(
                f"[限定词推荐] 来源: 历史, "
                f"determiner1: {history_det.get('determiner1_code', '')}, "
                f"determiner2: {history_det.get('determiner2_code', '')}"
            )
        else:
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
                    enames = []
                    for r in q_rank:
                        meta = self.store.get_qualifier_by_id(r["identifier"])
                        # 获取 code 字段（如 DJDW），而不是 inner_identifier
                        names.append(meta.get("cn_name", "") if meta else r["identifier"])
                        enames.append(meta.get("code", "") if meta else r["identifier"])
                    det_cnames.append(names)
                    det_enames.append(enames)
                    det_labels.append([0] * len(q_rank))
                    det_scores.append([r.get("score", 0) for r in q_rank])
                res["deteminer"] = {
                    "cname": det_cnames,
                    "ename": det_enames,
                    "label": det_labels,
                    "score": det_scores,
                }
                logger.info(
                    f"[限定词推荐] 来源: 向量+LLM, "
                    f"查询词: {det_queries}, "
                    f"结果数: {len(det_cnames)}"
                )
            else:
                logger.info(f"[限定词推荐] 无限定词查询，跳过")

        logger.info(
            f"[推荐完成] 数据元Top3: {element_cnames[:3]}, "
            f"限定词: {deteminers if deteminers else '无'}, "
            f"数据元编码: {element_codes[:3]}"
        )

        return res

    def _find_history_determiners(
        self,
        rankings: list[dict[str, Any]],
        history_det_map: dict[str, dict[str, str]],
    ) -> dict[str, str] | None:
        """从排序结果中查找首个具有历史限定词的元素。"""
        for rank in rankings:
            code = rank.get("element_code", "")
            if code in history_det_map:
                return history_det_map[code]
        return None

    def _build_history_deteminer(self, history_det: dict[str, str]) -> dict[str, Any]:
        """从历史限定词编码构建 deteminer 输出结构。

        输出格式与 common_fields.py 的 _run_det() 一致：
        {
            "cname": [["人员编号"], ...],
            "ename": [["RYBH"], ...],
            "label": [[0], ...],
            "score": [[1.0], ...]
        }
        """
        det_cnames, det_enames = [], []
        for code_key in ("determiner1_code", "determiner2_code"):
            code = history_det.get(code_key, "")
            if not code:
                continue
            meta = self.store.get_qualifier_by_id(code)
            # 获取 code 字段（如 DJDW），而不是 inner_identifier
            cn_name = meta.get("cn_name", "") if meta else code
            ename = meta.get("code", "") if meta else code
            det_cnames.append([cn_name])
            det_enames.append([ename])
        if not det_cnames:
            return {}
        return {
            "cname": det_cnames,
            "ename": det_enames,
            "label": [[0] for _ in det_cnames],
            "score": [[1.0] for _ in det_cnames],
        }

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
