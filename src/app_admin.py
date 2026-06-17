"""管理后台 Web 服务（端口 6070）。"""

from __future__ import annotations

import logging

from flask import Flask

from admin.routes import admin_bp
from config import settings
from logging_config import setup_logging

# 配置日志轮转
setup_logging(app_name="admin", level=logging.INFO, max_bytes=10*1024*1024, backup_count=5)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = settings.admin_secret_key
app.register_blueprint(admin_bp)


@app.context_processor
def inject_globals():
    return {"embedding_model": settings.embedding_model}


@app.route("/")
def root_redirect():
    from flask import redirect, url_for
    return redirect(url_for("admin.index"))
