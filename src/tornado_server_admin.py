import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.wsgi import WSGIContainer

from app_admin import app
from config import settings

if __name__ == "__main__":
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(settings.admin_port, address=settings.admin_host)
    print(f"管理后台已启动: http://{settings.admin_host}:{settings.admin_port}/admin")
    IOLoop.instance().start()
