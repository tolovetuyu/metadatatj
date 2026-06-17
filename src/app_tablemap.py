"""表/字段映射 HTTP 服务（端口 6061，接口与 quick 一致）。"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request

from knowledge_loader import load_knowledge
from logging_config import setup_logging
from services.table_mapper import TableMapper

# 配置日志轮转
setup_logging(app_name="tablemap", level=logging.INFO, max_bytes=10*1024*1024, backup_count=5)
logger = logging.getLogger(__name__)

app = Flask(__name__)
_mapper: TableMapper | None = None


def get_mapper() -> TableMapper:
    global _mapper
    if _mapper is None:
        kb = load_knowledge()
        _mapper = TableMapper(kb)
        logger.info("表映射服务初始化完成")
    return _mapper


@app.route("/autoexport/api/tableMap", methods=["POST"])
def table_map():
    data = request.get_json(force=True)
    return jsonify(get_mapper().table_map(data))


@app.route("/autoexport/api/fieldMap", methods=["POST"])
def field_map():
    data = request.get_json(force=True)
    return jsonify(get_mapper().field_map(data))
