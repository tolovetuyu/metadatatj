"""RUN 通用字段模板（与 quick commonFields 接口一致）。"""

from __future__ import annotations


def _run_det(*parts: tuple[tuple[str, str], ...]):
    return {
        "cname": [[p[0] for p in parts]],
        "ename": [[p[1] for p in parts]],
        "label": [[0 for _ in parts]],
        "score": [[1.0 for _ in parts]],
    }


def _item(cname, ename, typ, length, code, gz, det_parts=None):
    det = _run_det(*det_parts) if det_parts else _run_det(("RUN", "RUN"))
    return {
        "deteminer": det,
        "element": {
            "cname": cname,
            "ename": ename,
            "type": typ,
            "length": length,
            "classify": "9999999",
            "elementCode": code,
            "score": 1.0,
            "gz": gz,
            "gyh": "",
            "mapList": [],
            "deteminer": [],
            "deteminerEname": [],
        },
    }


def build_common_fields(data: dict) -> dict:
    pk = ",".join(data.get("primaryKeyFields", []))
    run_sjly = data.get("RUN_SJLYXTFLDM", "")
    run_xzqh = data.get("RUN_CJD_XZQHDM", "")
    run_mgjb = data.get("RUN_SJJLMGJB", "99")
    run_glht = data.get("RUN_GLHT_JYQK", "const('')") or "const('')"
    run_hsxx = data.get("RUN_HSXX_JYQK", "const('')") or "const('')"
    run_lyzy = data.get("RUN_LYZYBM", "")

    return {
        "recommendInfos": [
            _item("主记录ID", "ZJLID", "string", 128, "DE00003462", f"md5({pk})"),
            _item("数据来源系统分类代码", "SJLYXTFLDM", "string", 5, "DE00003464", f"const('{run_sjly}')"),
            _item("行政区划代码", "XZQHDM", "string", 6, "DE00000070", f"const('{run_xzqh}')",
                  det_parts=(("RUN", "RUN"), ("采集地", "CJD"))),
            _item("信息入库时间", "XXRKSJ", "long", 14, "DE00001080",
                  "format_date(format_systime('0'),'yyyyMMddHHmmss')"),
            _item("数据记录敏感级别", "SJJLMGJB", "string", 128, "DE00003463", f"const('{run_mgjb}')"),
            _item("错误数据详情", "CWSJXQ", "string", 4000, "DE0Z030018", "const('')"),
            _item("简要情况", "JYQK", "string", 4000, "DE00000521", run_glht,
                  det_parts=(("RUN", "RUN"), ("关联回填", "GLHT"))),
            _item("简要情况", "JYQK", "string", 4000, "DE00000521", run_hsxx,
                  det_parts=(("RUN", "RUN"), ("回溯信息", "HXSS"))),
            _item("采集时间", "CJSJ", "string", 14, "DE00000668", "",
                  det_parts=(("RUN", "RUN"), ("最近", "ZJ03"))),
            _item("标签编码", "BQBM", "string", 64, "DE00002276", "const('')"),
            _item("简要情况", "JYQK", "string", 4000, "DE00000521", "const('')",
                  det_parts=(("RUN", "RUN"), ("打标原因", "DBYY"))),
            _item("来源资源编码", "LYZYBM", "string", 14, "DE0Z030019", f"const('{run_lyzy}')"),
            _item("备注", "BZ", "string", 4000, "DE00000503", "const('')"),
            _item("信息编号", "XXBH", "string", 64, "DE00002001", "const('')",
                  det_parts=(("RUN", "RUN"), ("批次号", "PCH"))),
        ]
    }
