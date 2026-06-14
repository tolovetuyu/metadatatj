"""Excel 导入向量库：解析 → Embedding 向量化 → Chroma upsert。"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

from llm.client import EmbeddingClient
from vector.chroma_store import (
    COLLECTION_ELEMENTS,
    COLLECTION_QUALIFIERS,
    ChromaVectorStore,
)

logger = logging.getLogger(__name__)

ELEMENT_COLUMN_ALIASES = {
    "element_code": ["内部标识符", "element_code", "数据元内部标识符", "数据元标识符"],
    "cn_name": ["中文名称", "cn_name", "中文名称\n(*必填项)", "数据元中文名"],
    "en_name": ["标识符", "en_name", "英文名称", "数据项标识符", "标识符\n(*必填项)"],
    "type": ["类型", "type", "数据类型"],
    "length": ["长度", "length", "数据长度"],
    "classify": ["要素分类编码", "classify", "要素分类", "字段分类"],
}

QUALIFIER_COLUMN_ALIASES = {
    "identifier": ["标识符", "identifier", "限定词标识符", "限定词内部标识符"],
    "cn_name": ["中文名称", "cn_name", "限定词", "中文"],
}


class ImportKind(str, Enum):
    ELEMENTS = "elements"
    QUALIFIERS = "qualifiers"


class ImportMode(str, Enum):
    UPSERT = "upsert"
    APPEND = "append"
    REPLACE = "replace"


@dataclass
class ImportResult:
    kind: ImportKind
    mode: ImportMode
    total_rows: int
    imported: int
    skipped: int
    embedded: int
    errors: list[str] = field(default_factory=list)
    preview: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "mode": self.mode.value,
            "total_rows": self.total_rows,
            "imported": self.imported,
            "skipped": self.skipped,
            "embedded": self.embedded,
            "errors": self.errors,
            "preview": self.preview,
        }


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    cols = {c: c for c in df.columns}
    lower_map = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias in cols:
            return alias
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


def _map_columns(df: pd.DataFrame, alias_map: dict[str, list[str]]) -> pd.DataFrame:
    mapped: dict[str, pd.Series] = {}
    missing = []
    for target, aliases in alias_map.items():
        col = _find_column(df, aliases)
        if col is None:
            missing.append(target)
        else:
            mapped[target] = df[col].astype(str).str.strip()
    if missing:
        raise ValueError(f"缺少必要列（或别名不匹配）: {', '.join(missing)}；当前列: {list(df.columns)}")
    return pd.DataFrame(mapped).fillna("")


def _parse_length(val: str) -> int:
    if not val or val.lower() == "nan":
        return 0
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else 0


def _load_sheet(file_bytes: bytes, sheet_hint: str | None) -> pd.DataFrame:
    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    if sheet_hint and sheet_hint in xl.sheet_names:
        return _normalize_columns(pd.read_excel(xl, sheet_name=sheet_hint, dtype=str).fillna(""))
    if len(xl.sheet_names) == 1:
        return _normalize_columns(pd.read_excel(xl, sheet_name=0, dtype=str).fillna(""))
    for name in xl.sheet_names:
        if sheet_hint and sheet_hint in name:
            return _normalize_columns(pd.read_excel(xl, sheet_name=name, dtype=str).fillna(""))
    return _normalize_columns(pd.read_excel(xl, sheet_name=0, dtype=str).fillna(""))


def parse_elements_excel(file_bytes: bytes, sheet: str | None = None) -> pd.DataFrame:
    df = _load_sheet(file_bytes, sheet or "数据元")
    mapped = _map_columns(df, ELEMENT_COLUMN_ALIASES)
    mapped = mapped[mapped["element_code"].str.len() > 0]
    mapped = mapped[mapped["cn_name"].str.len() > 0]
    mapped["length"] = mapped["length"].map(_parse_length)
    return mapped.drop_duplicates(subset=["element_code"], keep="last")


def parse_qualifiers_excel(file_bytes: bytes, sheet: str | None = None) -> pd.DataFrame:
    df = _load_sheet(file_bytes, sheet or "限定词")
    mapped = _map_columns(df, QUALIFIER_COLUMN_ALIASES)
    mapped = mapped[mapped["identifier"].str.len() > 0]
    mapped = mapped[mapped["cn_name"].str.len() > 0]
    return mapped.drop_duplicates(subset=["identifier"], keep="last")


def _element_doc(row: dict[str, Any]) -> str:
    return (
        f"{row['element_code']} | {row['cn_name']} | {row.get('en_name', '')} | "
        f"{row.get('type', '')} | {row.get('length', 0)}"
    )


def _qualifier_doc(row: dict[str, Any]) -> str:
    return f"{row['identifier']} | {row['cn_name']}"


class ExcelVectorImporter:
    """导入时必须调用 Embedding：向量检索依赖入库向量与查询向量同一模型/空间。"""

    def __init__(
        self,
        store: ChromaVectorStore | None = None,
        embedder: EmbeddingClient | None = None,
    ) -> None:
        self.store = store or ChromaVectorStore()
        self.embedder = embedder or EmbeddingClient()

    def import_elements(
        self,
        file_bytes: bytes,
        mode: ImportMode = ImportMode.UPSERT,
        sheet: str | None = None,
    ) -> ImportResult:
        return self._import(
            kind=ImportKind.ELEMENTS,
            mode=mode,
            file_bytes=file_bytes,
            sheet=sheet,
            parser=parse_elements_excel,
            collection=COLLECTION_ELEMENTS,
            id_field="element_code",
            doc_fn=_element_doc,
            meta_fn=lambda r: {
                "element_code": r["element_code"],
                "cn_name": r["cn_name"],
                "en_name": r.get("en_name", ""),
                "type": r.get("type", "string"),
                "length": int(r.get("length", 0) or 0),
                "classify": r.get("classify", ""),
            },
        )

    def import_qualifiers(
        self,
        file_bytes: bytes,
        mode: ImportMode = ImportMode.UPSERT,
        sheet: str | None = None,
    ) -> ImportResult:
        return self._import(
            kind=ImportKind.QUALIFIERS,
            mode=mode,
            file_bytes=file_bytes,
            sheet=sheet,
            parser=parse_qualifiers_excel,
            collection=COLLECTION_QUALIFIERS,
            id_field="identifier",
            doc_fn=_qualifier_doc,
            meta_fn=lambda r: {"identifier": r["identifier"], "cn_name": r["cn_name"]},
        )

    def _import(
        self,
        kind: ImportKind,
        mode: ImportMode,
        file_bytes: bytes,
        sheet: str | None,
        parser,
        collection: str,
        id_field: str,
        doc_fn,
        meta_fn,
    ) -> ImportResult:
        result = ImportResult(kind=kind, mode=mode, total_rows=0, imported=0, skipped=0, embedded=0)
        try:
            df = parser(file_bytes, sheet)
        except Exception as exc:
            result.errors.append(str(exc))
            return result

        result.total_rows = len(df)
        if df.empty:
            result.errors.append("Excel 无有效数据行")
            return result

        rows = df.to_dict(orient="records")
        result.preview = rows[:10]

        if mode == ImportMode.REPLACE:
            self.store.reset_collection(collection)

        if mode == ImportMode.APPEND:
            col = self.store._collection(collection)
            existing = set()
            if col.count() > 0:
                existing = set(col.get(include=[])["ids"])
            rows = [r for r in rows if r[id_field] not in existing]
            result.skipped = result.total_rows - len(rows)

        if not rows:
            return result

        ids = [r[id_field] for r in rows]
        documents = [doc_fn(r) for r in rows]
        metadatas = [meta_fn(r) for r in rows]

        logger.info("开始 Embedding 向量化: %s 条 (%s)", len(documents), kind.value)
        embeddings = self.embedder.embed(documents)
        result.embedded = len(embeddings)

        self.store.upsert_batch(collection, ids, documents, metadatas, embeddings=embeddings)
        result.imported = len(ids)
        logger.info("导入完成: %s %s 条", kind.value, result.imported)
        return result


def build_template_excel(kind: ImportKind) -> bytes:
    buf = io.BytesIO()
    if kind == ImportKind.ELEMENTS:
        df = pd.DataFrame([
            {
                "内部标识符": "DE00000002",
                "中文名称": "姓名",
                "标识符": "XM",
                "类型": "字符型",
                "长度": "100",
                "要素分类编码": "010001",
            },
            {
                "内部标识符": "DE00000003",
                "中文名称": "姓名汉语拼音",
                "标识符": "XMHYPY",
                "类型": "字符型",
                "长度": "150",
                "要素分类编码": "010001",
            },
        ])
        sheet = "数据元"
    else:
        df = pd.DataFrame([
            {"标识符": "FQ", "中文名称": "父亲"},
            {"标识符": "RUN", "中文名称": "RUN"},
        ])
        sheet = "限定词"
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet, index=False)
    return buf.getvalue()
