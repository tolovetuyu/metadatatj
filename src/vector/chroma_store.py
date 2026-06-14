"""ChromaDB 向量库封装。

推荐 ChromaDB 的原因（本工程 ~2 万条量级）：
- 嵌入式部署，无需独立向量数据库服务
- 持久化到本地目录，索引构建一次即可
- 支持预计算 embedding 入库，查询时用同一 Embedding API
- 若后续规模到百万级，可迁移至 Qdrant / Milvus
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings
from llm.client import EmbeddingClient

logger = logging.getLogger(__name__)

COLLECTION_ELEMENTS = "data_elements"
COLLECTION_QUALIFIERS = "qualifiers"
COLLECTION_TABLES = "standard_tables"
COLLECTION_TABLE_FIELDS = "table_fields"


class ChromaVectorStore:
    def __init__(self, embedding_client: EmbeddingClient | None = None) -> None:
        settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embedder = embedding_client or EmbeddingClient()

    def _collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def reset_collection(self, name: str) -> None:
        try:
            self._client.delete_collection(name)
        except Exception:
            pass
        self._collection(name)

    def upsert_batch(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        col = self._collection(collection_name)
        if embeddings is None:
            embeddings = self._embedder.embed(documents)
        batch = 500
        for i in range(0, len(ids), batch):
            col.upsert(
                ids=ids[i : i + batch],
                documents=documents[i : i + batch],
                metadatas=metadatas[i : i + batch],
                embeddings=embeddings[i : i + batch],
            )

    def _query_with_embedding(
        self,
        collection_name: str,
        query_texts: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not query_texts:
            return []
        col = self._collection(collection_name)
        if col.count() == 0:
            logger.warning("集合 %s 为空，请先运行 scripts/build_index.py", collection_name)
            return []

        merged: dict[str, dict[str, Any]] = {}
        for text in query_texts:
            q_emb = self._embedder.embed_one(text)
            res = col.query(query_embeddings=[q_emb], n_results=min(top_k, col.count()))
            ids = res["ids"][0]
            distances = res["distances"][0]
            metas = res["metadatas"][0]
            for doc_id, dist, meta in zip(ids, distances, metas):
                score = 1.0 - float(dist)
                prev = merged.get(doc_id)
                if prev is None or score > prev["score"]:
                    merged[doc_id] = {**meta, "id": doc_id, "score": score}
        return sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]

    def search_elements(self, queries: list[str], top_k: int | None = None) -> list[dict[str, Any]]:
        return self._query_with_embedding(
            COLLECTION_ELEMENTS, queries, top_k or settings.recall_top_k
        )

    def search_qualifiers(self, queries: list[str], top_k: int | None = None) -> list[dict[str, Any]]:
        return self._query_with_embedding(
            COLLECTION_QUALIFIERS, queries, top_k or settings.recall_top_k
        )

    def search_tables(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._query_with_embedding(COLLECTION_TABLES, [query], top_k)

    def search_table_fields(
        self, table_ename: str, queries: list[str], top_k: int | None = None
    ) -> list[dict[str, Any]]:
        col = self._collection(COLLECTION_TABLE_FIELDS)
        if col.count() == 0:
            return []
        merged: dict[str, dict[str, Any]] = {}
        for text in queries:
            q_emb = self._embedder.embed_one(text)
            res = col.query(
                query_embeddings=[q_emb],
                n_results=min(top_k or settings.recall_top_k, col.count()),
                where={"table_ename": table_ename},
            )
            for doc_id, dist, meta in zip(res["ids"][0], res["distances"][0], res["metadatas"][0]):
                score = 1.0 - float(dist)
                prev = merged.get(doc_id)
                if prev is None or score > prev["score"]:
                    merged[doc_id] = {**meta, "id": doc_id, "score": score}
        return sorted(merged.values(), key=lambda x: x["score"], reverse=True)

    def get_element_by_code(self, element_code: str) -> dict[str, Any] | None:
        col = self._collection(COLLECTION_ELEMENTS)
        res = col.get(ids=[element_code])
        if not res["ids"]:
            return None
        return {**res["metadatas"][0], "id": res["ids"][0]}

    def get_qualifier_by_id(self, identifier: str) -> dict[str, Any] | None:
        col = self._collection(COLLECTION_QUALIFIERS)
        res = col.get(ids=[identifier])
        if not res["ids"]:
            return None
        return {**res["metadatas"][0], "id": res["ids"][0]}

    def count(self, collection_name: str) -> int:
        return self._collection(collection_name).count()

    def list_records(
        self,
        collection_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        col = self._collection(collection_name)
        total = col.count()
        if total == 0:
            return []
        res = col.get(limit=limit, offset=offset, include=["metadatas", "documents"])
        records = []
        for doc_id, meta, doc in zip(res["ids"], res["metadatas"], res["documents"]):
            records.append({"id": doc_id, "document": doc, **meta})
        return records

    def collection_stats(self) -> dict[str, int]:
        return {
            COLLECTION_ELEMENTS: self.count(COLLECTION_ELEMENTS),
            COLLECTION_QUALIFIERS: self.count(COLLECTION_QUALIFIERS),
            COLLECTION_TABLES: self.count(COLLECTION_TABLES),
            COLLECTION_TABLE_FIELDS: self.count(COLLECTION_TABLE_FIELDS),
        }
