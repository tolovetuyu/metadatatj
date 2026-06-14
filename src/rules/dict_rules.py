"""字典字段扩展与映射规则（与 quick funcs 对齐）。"""

from __future__ import annotations

from knowledge_loader import KnowledgeBase


DICT_SPECIAL_MAP = {
    "性别代码": ("性别（民族文字）", "XBMZWZ"),
    "民族代码": ("民族（民族文字）", "MZMZWZ"),
}

GYH_MAP = {
    "IP地址": "unify_ip",
    "办公电话": "unify_mobile",
    "非机动车号牌号码": "unify_car_number",
    "公民身份号码": "unify_idcard",
    "机动车号牌号码": "unify_car_number",
    "机动车驾驶证号": "unify_idcard",
    "联系电话": "unify_mobile",
    "移动电话": "unify_mobile",
    "银行卡号": "unify_bankcard",
    "住所电话": "unify_mobile",
    "固定电话": "unify_mobile",
}

ZK_CODES = [
    "婚姻状况", "兵役状况", "不在业状况", "尸体状况", "案/事件检材处置状况",
    "机动车安全状况", "道路路面状况", "消防设施状况", "手指异常状况", "健康状况",
    "从业状况", "残疾状况", "居住状况", "家庭经济状况", "职业状况", "消费状况",
    "活动状况", "现实状况", "表情状况", "姿势状况", "皮肤状况", "体温状况",
    "就学状况", "住房状况", "户籍状况", "监护状况", "运行状况",
]


def extend_field(cname: str, ename: str) -> list[tuple[str, str]]:
    if cname.endswith("代码"):
        res = [(cname, ename), (cname[:-2] + "名称", ename[:-2] + "MC")]
    else:
        res = [(cname + "代码", ename + "DM"), (cname + "名称", ename + "MC")]
    if res[0][0] in ("性别代码", "民族代码"):
        res[1] = DICT_SPECIAL_MAP.get(res[0][0], res[1])
    return res


def gen_dict_func(ename: str, func_list: list[str]) -> str:
    if not func_list:
        return ""
    item1 = ename
    item2 = func_list[0]
    map_func = f"refer_mapping({item1}, '{item2}')"
    for map_name in func_list[1:]:
        item1 = map_func
        map_func = f"refer_mapping({item1}, '{map_name}')"
    return map_func


def get_dict_fields(kb: KnowledgeBase, table_name: str) -> dict:
    fields = kb.dict_fields_info[kb.dict_fields_info["tableName"] == table_name.upper()]["fieldCode"].tolist()
    return {"dictFields": fields}


def get_dict_mapinfo(kb: KnowledgeBase, field_name: str, table_name: str) -> dict:
    field_name_origin = field_name
    field_name = field_name.upper()
    table_name = table_name.upper()
    table_name_new = table_name[:-2] if table_name.endswith(("_I", "_F")) else table_name

    temp = kb.df_source_dict_infor[kb.df_source_dict_infor["table_code_f.tbl_name"] == table_name_new]
    dict_name = temp[temp["table_code_f.col_name"] == field_name]["table_code_f.code_set"].tolist()
    res = {"mapList": [], "mapList_origin": [], "func": "", "func_origin": ""}
    if not dict_name:
        return res
    fir_name = dict_name[0]
    for item in kb.dict_api_paths:
        if item[0] == fir_name:
            res["mapList"] = item[1:]
            res["mapList_origin"] = item[1:][:-1]
            res["func"] = gen_dict_func(field_name_origin, res["mapList"])
            res["func_origin"] = gen_dict_func(field_name_origin, res["mapList"][:-1])
            break
    return res
