"""管理后台路由。"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for
from io import BytesIO

from config import settings
from services.excel_importer import (
    ExcelVectorImporter,
    ImportKind,
    ImportMode,
    build_template_excel,
)
from vector.chroma_store import COLLECTION_ELEMENTS, COLLECTION_QUALIFIERS, ChromaVectorStore

logger = logging.getLogger(__name__)

admin_bp = Blueprint(
    "admin",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/admin",
)


def _store() -> ChromaVectorStore:
    return ChromaVectorStore()


@admin_bp.route("/", strict_slashes=False)
def index():
    stats = _store().collection_stats()
    return render_template(
        "index.html",
        stats=stats,
        embedding_model=settings.embedding_model,
        chroma_dir=str(settings.chroma_persist_dir),
    )


@admin_bp.route("/import")
def import_page():
    return render_template(
        "import.html",
        embedding_model=settings.embedding_model,
        batch_size=settings.embedding_batch_size,
    )


@admin_bp.route("/browse/<kind>")
def browse(kind: str):
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    offset = (page - 1) * per_page
    if kind == "elements":
        collection = COLLECTION_ELEMENTS
        title = "数据元"
    elif kind == "qualifiers":
        collection = COLLECTION_QUALIFIERS
        title = "限定词"
    else:
        flash("未知类型", "error")
        return redirect(url_for("admin.index"))

    store = _store()
    total = store.count(collection)
    records = store.list_records(collection, limit=per_page, offset=offset)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "browse.html",
        kind=kind,
        title=title,
        records=records,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@admin_bp.route("/import/submit", methods=["POST"])
def import_submit():
    kind_str = request.form.get("kind", "")
    mode_str = request.form.get("mode", "upsert")
    sheet = request.form.get("sheet", "").strip() or None
    file = request.files.get("file")

    if not file or not file.filename:
        flash("请选择 Excel 文件", "error")
        return redirect(url_for("admin.import_page"))

    try:
        kind = ImportKind(kind_str)
        mode = ImportMode(mode_str)
    except ValueError:
        flash("导入类型或模式无效", "error")
        return redirect(url_for("admin.import_page"))

    file_bytes = file.read()
    _archive_upload(kind, file.filename, file_bytes)

    importer = ExcelVectorImporter()
    try:
        if kind == ImportKind.ELEMENTS:
            result = importer.import_elements(file_bytes, mode=mode, sheet=sheet)
        else:
            result = importer.import_qualifiers(file_bytes, mode=mode, sheet=sheet)
    except Exception as exc:
        logger.exception("导入失败")
        flash(f"导入失败: {exc}", "error")
        return redirect(url_for("admin.import_page"))

    if result.errors:
        flash("; ".join(result.errors), "error")
        return redirect(url_for("admin.import_page"))

    flash(
        f"导入成功：共 {result.total_rows} 行，写入 {result.imported} 条，"
        f"跳过 {result.skipped} 条，已向量化 {result.embedded} 条",
        "success",
    )
    return render_template("import_result.html", result=result)


@admin_bp.route("/api/stats")
def api_stats():
    return jsonify(_store().collection_stats())


@admin_bp.route("/template/<kind>")
def download_template(kind: str):
    try:
        ik = ImportKind.ELEMENTS if kind == "elements" else ImportKind.QUALIFIERS
    except ValueError:
        return jsonify({"error": "invalid kind"}), 400
    data = build_template_excel(ik)
    filename = "数据元导入模板.xlsx" if ik == ImportKind.ELEMENTS else "限定词导入模板.xlsx"
    return send_file(
        BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


def _archive_upload(kind: ImportKind, filename: str, data: bytes) -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(filename).name.replace(" ", "_")
    path = settings.upload_dir / f"{ts}_{kind.value}_{safe_name}"
    path.write_bytes(data)
