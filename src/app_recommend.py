"""数据元/限定词推荐 HTTP 服务（端口 6058，接口与 quick 一致）。"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request

from config import settings
from knowledge_loader import load_knowledge
from services.common_fields import build_common_fields
from services.history_recommender import get_history_recommender
from services.recommender import MetadataRecommender
from services.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
_recommender: MetadataRecommender | None = None


def get_recommender() -> MetadataRecommender:
    global _recommender
    if _recommender is None:
        kb = load_knowledge()
        _recommender = MetadataRecommender(kb)
        logger.info("推荐服务初始化完成")

        # 加载历史推荐缓存
        if settings.history_recommend_enabled:
            history = get_history_recommender()
            count = history.load_cache()
            logger.info(f"历史推荐缓存加载完成，共 {count} 条记录")
            # 启动定时同步任务
            start_scheduler()

    return _recommender


@app.route("/autoexport/api/recommend", methods=["POST"])
def recommend():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "输入参数异常！"})
    fields = data.get("fieldsInfo", [])
    result = get_recommender().recommend_batch(fields, with_extend=False)
    return jsonify(result)


@app.route("/autoexport/api/recommendWithExtend", methods=["POST"])
def recommend_with_extend():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "输入参数异常！"})
    fields = data.get("fieldsInfo", [])
    lyb = data.get("lybEname", "").upper()
    result = get_recommender().recommend_batch(fields, lyb_ename=lyb, with_extend=True)
    return jsonify(result)


@app.route("/autoexport/api/commonFields", methods=["POST"])
def common_fields():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "输入参数异常！"})
    return jsonify(build_common_fields(data))


@app.route("/autoexport/api/history/stats", methods=["GET"])
def history_stats():
    """获取历史推荐缓存统计信息。"""
    history = get_history_recommender()
    return jsonify(history.get_cache_stats())


@app.route("/autoexport/api/history/sync", methods=["POST"])
def history_sync():
    """手动触发历史推荐同步。

    请求参数:
        force_full: 是否强制全量同步（默认false，增量同步）
        source: 同步数据源，"task_process"（默认）或 "mapping_history" 或 "all"
    """
    from services.history_sync import get_sync_service
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    force_full = data.get("force_full", False)
    source = data.get("source", "task_process")

    sync_service = get_sync_service()
    result = {}

    if source in ("task_process", "all"):
        result = sync_service.sync_from_task_process(force_full=force_full)
    if source in ("mapping_history", "all"):
        history_result = sync_service.sync_from_history(force_full=force_full)
        if source == "all":
            result["history_sync"] = history_result
        else:
            result = history_result

    # 同步完成后刷新缓存
    if result.get("status") == "success":
        history = get_history_recommender()
        history.load_cache()
    return jsonify(result)
