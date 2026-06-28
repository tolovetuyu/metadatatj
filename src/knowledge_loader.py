"""加载 quick 知识库 Excel / CSV / 数据库。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config import settings


def _load_from_db() -> KnowledgeBase:
    """从数据库加载知识库。"""
    import db

    # 加载数据元（使用 rucp_element_biaozhun 表）
    rows = db.query_all(
        "SELECT code, chname, enname, type, length, valuetype, interalcode "
        "FROM rucp_element_biaozhun WHERE state = '1' AND up_to_date = 1"
    )
    if rows:
        element_items = pd.DataFrame(rows)
        element_items.columns = ["element_code", "cn_name", "en_name", "type", "length", "classify", "inner_code"]
    else:
        element_items = pd.DataFrame(columns=["element_code", "cn_name", "en_name", "type", "length", "classify", "inner_code"])
    element_items["length"] = element_items["length"].fillna(0).apply(
        lambda x: int(str(x).replace("c", "").replace("..", "").split(",")[0]) if str(x).strip() else 0
    )

    # 加载限定词
    rows = db.query_all(
        "SELECT chname, code, interalcode FROM rucp_element_determiner WHERE state = '1' and up_to_date = 1"
    )
    if rows:
        determine_items = pd.DataFrame(rows)
        if len(determine_items.columns) == 3:
            determine_items.columns = ["cn_name", "identifier", "inner_identifier"]
        elif len(determine_items.columns) == 2:
            determine_items.columns = ["cn_name", "identifier"]
            determine_items["inner_identifier"] = ""
        else:
            logger.warning(f"限定词查询返回 {len(determine_items.columns)} 列，预期2-3列")
            determine_items = pd.DataFrame(columns=["cn_name", "identifier", "inner_identifier"])
    else:
        determine_items = pd.DataFrame(columns=["cn_name", "identifier", "inner_identifier"])

    # 构建gz_map
    gz_map: dict[str, str] = {}
    for item in element_items["cn_name"]:
        if str(item).endswith("时间"):
            gz_map[item] = "format_date({0},'{1}')"
        if str(item).endswith("日期"):
            gz_map[item] = "format_date({0},'{1}')"

    # 加载表目录
    rows = db.query_all(
        "SELECT DISTINCT t.CODE, t.chname, t.enname FROM rucp_standard_dataset t "
        "INNER JOIN rucp_standard_class t2 ON t.standardclass = t2.id "
        "INNER JOIN rucp_setting_base t3 ON t3.type = t2.code AND t3.isuse = 1 "
        "WHERE t.STATUS = '1'"
    )
    if rows:
        table_catalog = pd.DataFrame(rows)
        table_catalog.columns = ["0", "1", "2"]
    else:
        table_catalog = pd.DataFrame(columns=["0", "1", "2"])
    # 添加空列以兼容原有格式
    table_catalog["3"] = table_catalog["1"]
    table_catalog["4"] = ""

    # 字典字段信息（从文件加载，因为数据库中没有对应表）
    dict_fields_info, dict_api_paths, df_source_dict_infor = _load_dict_info_from_file()

    return KnowledgeBase(
        element_items=element_items,
        determine_items=determine_items,
        gz_map=gz_map,
        table_catalog=table_catalog,
        dict_fields_info=dict_fields_info,
        dict_api_paths=dict_api_paths,
        df_source_dict_infor=df_source_dict_infor,
    )


def _load_dict_info_from_file() -> tuple[pd.DataFrame, list, pd.DataFrame]:
    """从文件加载字典字段信息（即使 DATA_SOURCE=db 也需要）。"""
    import numpy as np

    kb = settings.knowledge_dir
    dict_file = kb / "dict" / "table_code_f.csv"
    api_file = kb / "dict" / "df_api.npy"

    # 如果文件不存在，返回空数据
    if not dict_file.exists():
        return pd.DataFrame(columns=["tableName", "fieldCode"]), [], pd.DataFrame()

    # 加载字典字段配置
    df_source_dict_infor = pd.read_csv(dict_file, dtype=str).fillna("")
    df_source_dict_infor["table_code_f.tbl_name"] = df_source_dict_infor["table_code_f.tbl_name"].map(
        lambda x: x.upper()
    )
    df_source_dict_infor["table_code_f.col_name"] = df_source_dict_infor["table_code_f.col_name"].map(
        lambda x: x.upper()
    )

    # 构建字典字段列表（is_code 是字符串 "TRUE" 或 "FALSE"）
    dict_fields_info = df_source_dict_infor[df_source_dict_infor["table_code_f.is_code"] == "TRUE"][  # noqa: E712
        ["table_code_f.tbl_name", "table_code_f.col_name"]
    ].drop_duplicates().copy()
    dict_fields_info.columns = ["tableName", "fieldCode"]

    # 加载字典映射路径
    dict_api_paths = list(np.load(api_file, allow_pickle=True)) if api_file.exists() else []

    return dict_fields_info, dict_api_paths, df_source_dict_infor


@dataclass
class KnowledgeBase:
    element_items: pd.DataFrame
    determine_items: pd.DataFrame
    gz_map: dict[str, str]
    table_catalog: pd.DataFrame
    dict_fields_info: pd.DataFrame
    dict_api_paths: list
    df_source_dict_infor: pd.DataFrame


def _knowledge_path(*parts: str) -> Path:
    return settings.knowledge_dir.joinpath(*parts)


def load_knowledge() -> KnowledgeBase:
    """加载知识库，根据配置选择数据源。"""
    if settings.data_source == "db":
        return _load_from_db()
    return _load_from_file()


def _load_from_file() -> KnowledgeBase:
    """从文件加载知识库。"""
    kb = settings.knowledge_dir
    if not kb.exists():
        raise FileNotFoundError(f"知识库目录不存在: {kb}，请在 .env 中配置 KNOWLEDGE_DIR")

    elements_path = _knowledge_path("01_公安标准数据元和限定词_v2.xlsx")
    elements = pd.read_excel(elements_path, sheet_name="数据元", dtype=str).fillna("")
    element_items = elements[
        ["中文名称\n(*必填项)", "标识符\n(*必填项)", "类型", "长度", "要素分类编码", "内部标识符\n(*必填项)"]
    ].copy()
    # 修正列名映射，与数据库加载保持一致
    element_items.columns = ["cn_name", "element_code", "type", "length", "classify", "inner_code"]
    # 添加 en_name 字段（拼音），用于文档生成
    element_items["en_name"] = ""
    element_items["length"] = element_items["length"].map(
        lambda x: int(str(x).split(",")[0]) if str(x).strip() else 0
    )

    det_path = _knowledge_path("01_公安标准限定词.xlsx")
    if det_path.exists():
        determine_items = pd.read_excel(det_path, dtype=str).fillna("")
    else:
        determine_items = pd.read_excel(
            elements_path, sheet_name="限定词", dtype=str
        ).fillna("")[["中文名称", "标识符"]].copy()
    determine_items.columns = ["cn_name", "identifier"]

    gz_map: dict[str, str] = {}
    for item in elements["中文名称\n(*必填项)"]:
        if item.endswith("时间"):
            gz_map[item] = "format_date({0},'{1}')"
        if item.endswith("日期"):
            gz_map[item] = "format_date({0},'{1}')"

    table_catalog = pd.read_excel(_knowledge_path("01_标准库数据集.xlsx"), sheet_name="目录", dtype=str).fillna("")
    len_cols = len(table_catalog.columns)
    table_catalog.columns = [str(i) for i in range(len_cols)]

    # 字典字段信息（从文件加载）
    dict_fields_info, dict_api_paths, df_source_dict_infor = _load_dict_info_from_file()

    return KnowledgeBase(
        element_items=element_items,
        determine_items=determine_items,
        gz_map=gz_map,
        table_catalog=table_catalog,
        dict_fields_info=dict_fields_info,
        dict_api_paths=dict_api_paths,
        df_source_dict_infor=df_source_dict_infor,
    )


def load_table_fields(table_ename: str) -> pd.DataFrame:
    """加载表字段信息，根据配置选择数据源。"""
    if settings.data_source == "db":
        return _load_table_fields_from_db(table_ename)
    return _load_table_fields_from_file(table_ename)


def _load_table_fields_from_db(table_ename: str) -> pd.DataFrame:
    """从数据库加载表字段信息。"""
    import db

    # 先获取表ID
    row = db.query_one(
        "SELECT id FROM rucp_standard_dataset WHERE enname = %s AND status = '1'",
        (table_ename,)
    )
    if not row:
        return pd.DataFrame()

    dataset_id = row["id"]
    rows = db.query_all(
        "SELECT DISTINCT seq, chname, enname, description, determiner1, determiner2, "
        "bzeleid, elementid, bzele_cname, type, length, codeset, isrequire, default_value, "
        "ismultivalue, isindex, isunique, dataclass, safelevel, '', remark1, '' "
        "FROM rucp_standard_dataset_ele WHERE datasetid = %s ORDER BY seq",
        (dataset_id,)
    )
    df_target = pd.DataFrame(rows)
    if df_target.empty:
        return df_target
    s_columns = [
        "序号", "数据项中文名", "数据项英文名", "数据项描述", "限定词标识符1",
        "限定词标识符2", "数据元内部标识符", "数据项英文名", "数据元中文名",
        "数据类型", "数据长度", "引用代码集", "是否必填", "默认值", "是否多值",
        "是否查询", "是否唯一", "分类", "分级", "归并维度", "备注", "主记录ID生成",
    ]
    df_target.columns = s_columns[: len(df_target.columns)]
    return df_target


def _load_table_fields_from_file(table_ename: str) -> pd.DataFrame:
    """从文件加载表字段信息。"""
    df_target = pd.read_excel(
        _knowledge_path("01_标准库数据集.xlsx"), sheet_name=table_ename, dtype=str
    ).fillna("")
    s_columns = [
        "序号", "数据项中文名", "数据项标识符", "数据项描述", "限定词内部标识符",
        "限定词标识符", "限定词", "数据元内部标识符", "数据元标识符", "数据元中文名",
        "数据类型", "数据长度", "引用代码集", "是否必填", "默认值", "是否多值",
        "是否查询", "是否唯一", "分类", "分级", "归并维度", "备注", "主记录ID生成",
    ]
    df_target.columns = s_columns[:10] + list(df_target.columns)[10:]
    return df_target
