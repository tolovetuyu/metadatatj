"""数据元/限定词推荐 HTTP 服务（端口 6058，接口与 quick 一致）。"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request

from config import settings
from knowledge_loader import load_knowledge
from logging_config import setup_logging
from services.common_fields import build_common_fields
from services.data_quality_analyzer import get_data_quality_analyzer
from services.dict_recommender import get_dict_recommender
from services.field_name_recommender import get_field_name_recommender
from services.history_recommender import get_history_recommender
from services.recommender import MetadataRecommender
from services.scheduler import start_scheduler
from vector.chroma_store import ChromaVectorStore

# 配置日志轮转
setup_logging(app_name="recommend", level=logging.INFO, max_bytes=10*1024*1024, backup_count=5)
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


@app.route("/autoexport/api/dataQuality/analyze", methods=["POST"])
def data_quality_analyze():
    """分析数据质量并获取治理建议。

    请求参数:
        dataset_name: 数据集/表名称
        fields_info: 字段信息列表，每个字段包含 quality 信息
            - field_name: 字段名称
            - chname: 中文名称
            - field_type: 字段类型
            - fill_rate: 填充率
            - data_type_rate: 类型符合率
            - dict_rate: 字典符合率
            - entity_rate: 命名实体合规率
            - most_appear: 出现最多的值
            - sample_count: 样例数量
            - required_fill_rate: 必填项填充率

    返回:
        LLM 生成的数据治理建议
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "输入参数异常！"})

    dataset_name = data.get("dataset_name", "Unknown")
    fields_info = data.get("fields_info", [])

    if not fields_info:
        return jsonify({"error": "fields_info 不能为空！"})

    try:
        analyzer = get_data_quality_analyzer()
        result = analyzer.analyze(dataset_name, fields_info)
        # 直接返回纯文本
        return result.get("recommendations", "")
    except Exception as e:
        logger.error(f"数据质量分析失败: {e}")
        return str(e)


@app.route("/autoexport/api/fieldName/recommend", methods=["POST"])
def field_name_recommend():
    """根据字段英文名推荐中文名。

    请求参数:
        field_names: 字段英文名列表，如 ["user_name", "user_age", "create_time"]

    返回:
        LLM 生成的字段中文名推荐
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "输入参数异常！"})

    field_names = data.get("field_names", [])

    if not field_names:
        return jsonify({"error": "field_names 不能为空！"})

    try:
        recommender = get_field_name_recommender()
        result = recommender.recommend(field_names)
        return jsonify(result)
    except Exception as e:
        logger.error(f"字段名称推荐失败: {e}")
        return jsonify({"error": str(e)})


@app.route("/autoexport/api/dict/recommend", methods=["POST"])
def dict_recommend():
    """根据枚举值推荐字典。

    请求参数:
        enum_values: 枚举值列表，如 ["男", "女"]
        top_k: 返回前几个推荐（默认 5）

    返回:
        推荐的字典列表，包含匹配数和可信度
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "输入参数异常！"})

    enum_values = data.get("enum_values", [])
    top_k = data.get("top_k", 5)

    if not enum_values:
        return jsonify({"error": "enum_values 不能为空！"})

    try:
        store = ChromaVectorStore()
        recommender = get_dict_recommender(store)
        result = recommender.recommend(enum_values, top_k)
        logger.info(f"字典推荐完成，枚举值: {enum_values}, 推荐数: {len(result)}")
        return jsonify({"recommendations": result})
    except Exception as e:
        logger.error(f"字典推荐失败: {e}")
        return jsonify({"error": str(e)})


@app.route("/autoexport/api/vectorIndex/rebuild", methods=["POST"])
def vector_index_rebuild():
    """手动触发向量库全量重建。

    注意：此操作会清空并重建向量库，期间服务可能短暂不可用。

    请求参数:
        collections: 要重建的集合列表，可选值：
            - "elements": 数据元
            - "qualifiers": 限定词
            - "tables": 标准表
            - "table_fields": 表字段
            - "dict_items": 字典项
            - "all": 全部（默认）

    返回:
        重建结果统计
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}

    collections = data.get("collections", ["all"])
    if isinstance(collections, str):
        collections = [collections]

    # 验证参数
    valid_collections = ["elements", "qualifiers", "tables", "table_fields", "dict_items", "all"]
    for c in collections:
        if c not in valid_collections:
            return jsonify({"error": f"无效的集合名称: {c}，有效值: {valid_collections}"})

    try:
        logger.info(f"[向量库重建] 开始重建，集合: {collections}")
        
        # 动态导入，避免循环依赖
        import subprocess
        import sys
        from pathlib import Path
        
        # 获取项目根目录
        root = Path(__file__).resolve().parent.parent
        
        # 执行重建脚本
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "build_index.py")],
            capture_output=True,
            text=True,
            cwd=str(root)
        )
        
        if result.returncode != 0:
            logger.error(f"[向量库重建] 失败: {result.stderr}")
            return jsonify({
                "status": "error",
                "message": "向量库重建失败",
                "error": result.stderr
            })
        
        logger.info(f"[向量库重建] 完成: {result.stdout}")
        
        # 重建完成后重新加载推荐器
        global _recommender
        _recommender = None
        get_recommender()
        
        return jsonify({
            "status": "success",
            "message": "向量库重建完成",
            "output": result.stdout
        })
        
    except Exception as e:
        logger.error(f"[向量库重建] 异常: {e}")
        return jsonify({"error": str(e)})
