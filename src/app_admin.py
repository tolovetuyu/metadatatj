"""管理后台 Web 服务（端口 6070）。"""

from __future__ import annotations

import logging

from flask import Flask

from admin.routes import admin_bp
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
