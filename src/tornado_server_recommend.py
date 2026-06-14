import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.wsgi import WSGIContainer

from app_recommend import app
from config import settings

if __name__ == "__main__":
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(settings.recommend_port, address=settings.recommend_host)
    print(f"推荐服务已启动: http://{settings.recommend_host}:{settings.recommend_port}")
    IOLoop.instance().start()
