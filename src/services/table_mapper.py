"""地方库 → 标准库表/字段映射。"""

from __future__ import annotations

import re

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from config import settings
from knowledge_loader import KnowledgeBase, load_table_fields
from llm.client import EmbeddingClient
from vector.chroma_store import ChromaVectorStore

PUNCTUATION = """!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"""


class TableMapper:
    def __init__(
        self,
        kb: KnowledgeBase,
        store: ChromaVectorStore | None = None,
        embedder: EmbeddingClient | None = None,
    ) -> None:
        self.kb = kb
        self.store = store or ChromaVectorStore()
        self.embedder = embedder or EmbeddingClient()
        self._catalog = kb.table_catalog

    def _clean(self, text: str) -> str:
        return re.sub(r"[{}]+".format(PUNCTUATION), "", text)

    def _encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.array([])
        return np.array(self.embedder.embed(texts), dtype=np.float64)

    def resolve_table(self, source_table_name: str) -> list:
        df_s = self._catalog["1"].tolist()
        df_t = self._catalog["3"].tolist()
        df_e = self._catalog["2"].tolist()
        if source_table_name in df_s:
            i = df_s.index(source_table_name)
            if df_t[i] != "自定义":
                return [source_table_name, df_t[i], df_e[i], 1.0]
        hits = self.store.search_tables(source_table_name, top_k=1)
        if hits:
            h = hits[0]
            return [source_table_name, h.get("cn_name", ""), h.get("en_name", ""), h.get("score", 0)]
        return [source_table_name, "", "", 0.0]

    def _field_mapping(
        self,
        source_fields: list[str],
        target_names: list[str],
        limit_score: float,
    ) -> dict:
        source_clean = [self._clean(x) for x in source_fields]
        target_clean = [self._clean(x) for x in target_names]

        src_emb = self._encode(source_clean)
        tgt_emb = self._encode(target_clean)
        if src_emb.size == 0 or tgt_emb.size == 0:
            return {}

        sim = cosine_similarity(tgt_emb, src_emb).astype(np.float64)
        test_list = list(sim)
        top_n = []
        pairs = []
        for i, score_i in enumerate(test_list):
            scored = [(j, max(score_i[j], 0.0)) for j in range(len(score_i))]
            scored.sort(key=lambda x: x[1], reverse=True)
            top_n.append(scored)
            for j in range(len(test_list[0])):
                pairs.append([i, j, test_list[i][j]])
        pairs.sort(key=lambda x: x[2], reverse=True)

        used_i, used_j, matched = set(), set(), []
        for i, j, score in pairs:
            if len(used_i) >= len(test_list) or len(used_j) >= len(test_list[0]):
                break
            if i in used_i or j in used_j:
                continue
            if score < limit_score:
                break
            matched.append([i, j, score])
            used_i.add(i)
            used_j.add(j)

        res: dict = {}
        matched.sort(key=lambda x: x[0])
        stacked = set()
        for ti, si, score in matched:
            res[target_names[ti]] = {
                "recommend": {"cname": source_fields[si], "score": float(score)}
            }
            stacked.add(ti)
        for i, name in enumerate(target_names):
            if i not in stacked:
                res[name] = {"recommend": {"cname": "", "score": 0.0}}

        for i, name in enumerate(target_names):
            top = top_n[i]
            res[name]["topN"] = {
                "cnames": [source_fields[j] for j, _ in top],
                "scores": [float(s) for _, s in top],
            }
        return res

    def table_map(self, data: dict) -> dict:
        source_name = data.get("dbkCname", "")
        source_fields = data.get("dbkFields", [])
        limit_score = float(data.get("fLimitScore", settings.field_match_threshold))
        tlimit = float(data.get("tLimitScore", settings.table_match_threshold))

        info = self.resolve_table(source_name)
        res = {"dbkCname": source_name}
        if info[3] < tlimit:
            return res

        res["yskCname"] = info[1]
        res["yskEname"] = info[2]
        res["tableMatchScore"] = info[3]
        df = load_table_fields(info[2])
        target_names = df["数据项中文名"].tolist()
        res["recommendInfos"] = self._field_mapping(source_fields, target_names, limit_score)
        return res

    def field_map(self, data: dict) -> dict:
        source_name = data.get("dbkCname", "")
        source_fields = data.get("dbkFields", [])
        ysk_cname = data.get("yskCname", "")
        ysk_ename = data.get("yskEname", "")
        limit_score = float(data.get("fLimitScore", settings.field_match_threshold))

        res = {
            "dbkCname": source_name,
            "yskCname": ysk_cname,
            "yskEname": ysk_ename,
        }
        df = load_table_fields(ysk_ename)
        target_names = df["数据项中文名"].tolist()
        res["recommendInfos"] = self._field_mapping(source_fields, target_names, limit_score)
        return res
