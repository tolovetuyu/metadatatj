"""构建 Chroma 向量索引。首次部署或知识库更新后执行。

用法（在项目根目录）:
  python scripts/build_index.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from config import settings
from knowledge_loader import load_knowledge, load_table_fields
from llm.client import EmbeddingClient
from vector.chroma_store import (
    COLLECTION_ELEMENTS,
    COLLECTION_QUALIFIERS,
    COLLECTION_TABLE_FIELDS,
    COLLECTION_TABLES,
    ChromaVectorStore,
)


def _element_doc(row) -> str:
    return f"{row.element_code} | {row.cn_name} | {row.en_name} | {row.type} | {row.length}"


def _qualifier_doc(row) -> str:
    return f"{row.identifier} | {row.cn_name}"


def build_elements(store: ChromaVectorStore, kb) -> None:
    df = kb.element_items
    store.reset_collection(COLLECTION_ELEMENTS)
    ids = df["element_code"].tolist()
    docs = [_element_doc(row) for row in df.itertuples()]
    metas = [
        {
            "element_code": row.element_code,
            "cn_name": row.cn_name,
            "en_name": row.en_name,
            "type": row.type,
            "length": int(row.length),
            "classify": row.classify,
        }
        for row in df.itertuples()
    ]
    store.upsert_batch(COLLECTION_ELEMENTS, ids, docs, metas)
    print(f"  数据元: {len(ids)} 条")


def build_qualifiers(store: ChromaVectorStore, kb) -> None:
    df = kb.determine_items.drop_duplicates(subset=["identifier"])
    store.reset_collection(COLLECTION_QUALIFIERS)
    ids = df["identifier"].tolist()
    docs = [_qualifier_doc(row) for row in df.itertuples()]
    metas = [{"identifier": row.identifier, "cn_name": row.cn_name} for row in df.itertuples()]
    store.upsert_batch(COLLECTION_QUALIFIERS, ids, docs, metas)
    print(f"  限定词: {len(ids)} 条")


def build_tables(store: ChromaVectorStore, kb) -> None:
    cat = kb.table_catalog
    cn_names = cat["3"].tolist()
    en_names = cat["2"].tolist()
    source_names = cat["1"].tolist()
    store.reset_collection(COLLECTION_TABLES)
    ids, docs, metas = [], [], []
    seen_ids = set()  # 用于去重
    for src, cn, en in zip(source_names, cn_names, en_names):
        if not cn or cn == "自定义":
            continue
        doc_id = en or cn
        # 跳过重复的 ID
        if doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)
        ids.append(doc_id)
        docs.append(f"{cn} | {en} | {src}")
        metas.append({"cn_name": cn, "en_name": en, "source_name": src})
    store.upsert_batch(COLLECTION_TABLES, ids, docs, metas)
    print(f"  标准表: {len(ids)} 条")


def build_table_fields(store: ChromaVectorStore, kb) -> None:
    cat = kb.table_catalog
    en_names = [e for e in cat["2"].tolist() if e and e != "自定义"]
    store.reset_collection(COLLECTION_TABLE_FIELDS)
    ids, docs, metas = [], [], []
    for en in en_names:
        try:
            df = load_table_fields(en)
        except Exception as exc:
            print(f"  跳过表 {en}: {exc}")
            continue
        for row in df.itertuples():
            field_cn = getattr(row, "数据项中文名", "")
            field_en = getattr(row, "数据项标识符", "")
            if not field_cn:
                continue
            doc_id = f"{en}::{field_en or field_cn}"
            ids.append(doc_id)
            docs.append(f"{field_cn} | {field_en} | {en}")
            metas.append({
                "table_ename": en,
                "field_cn": field_cn,
                "field_en": field_en,
            })
    if ids:
        store.upsert_batch(COLLECTION_TABLE_FIELDS, ids, docs, metas)
    print(f"  表字段: {len(ids)} 条")


def main() -> None:
    print(f"知识库: {settings.knowledge_dir}")
    print(f"向量库: {settings.chroma_persist_dir}")
    kb = load_knowledge()
    embedder = EmbeddingClient()
    store = ChromaVectorStore(embedder)
    print("构建索引...")
    build_elements(store, kb)
    build_qualifiers(store, kb)
    build_tables(store, kb)
    build_table_fields(store, kb)
    print("完成。")


if __name__ == "__main__":
    main()
