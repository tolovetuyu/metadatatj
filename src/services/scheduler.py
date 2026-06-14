"""定时任务调度器。

负责定时同步历史推荐统计数据。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable

from config import settings
from services.history_recommender import get_history_recommender
from services.history_sync import get_sync_service

logger = logging.getLogger(__name__)


class Scheduler:
    """定时任务调度器。"""

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._tasks: list[dict] = []

    def add_task(
        self,
        name: str,
        func: Callable,
        interval_hours: float = 24,
        run_at_start: bool = False,
    ) -> None:
        """添加定时任务。"""
        self._tasks.append({
            "name": name,
            "func": func,
            "interval_hours": interval_hours,
            "run_at_start": run_at_start,
            "last_run": None,
        })

    def _run_task(self, task: dict) -> None:
        """执行单个任务。"""
        try:
            logger.info(f"开始执行任务: {task['name']}")
            result = task["func"]()
            task["last_run"] = datetime.now()
            logger.info(f"任务完成: {task['name']}, 结果: {result}")
        except Exception as e:
            logger.error(f"任务执行失败: {task['name']}, 错误: {e}")

    def _scheduler_loop(self) -> None:
        """调度循环。"""
        logger.info("定时任务调度器启动")

        # 启动时执行标记了 run_at_start 的任务
        for task in self._tasks:
            if task["run_at_start"]:
                self._run_task(task)

        while self._running:
            now = datetime.now()

            for task in self._tasks:
                last_run = task["last_run"]
                interval = timedelta(hours=task["interval_hours"])

                if last_run is None or (now - last_run) >= interval:
                    self._run_task(task)

            # 每分钟检查一次
            time.sleep(60)

        logger.info("定时任务调度器停止")

    def start(self) -> None:
        """启动调度器。"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止调度器。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)


def sync_history_recommend(force_full: bool = False) -> dict:
    """同步历史推荐统计数据任务。
    
    Args:
        force_full: 是否强制全量同步
    """
    sync_service = get_sync_service()
    result = sync_service.sync_from_history(force_full=force_full)

    # 同步完成后刷新缓存
    if result.get("status") == "success":
        recommender = get_history_recommender()
        recommender.load_cache()

    return result


def load_history_cache() -> int:
    """加载历史推荐缓存任务。"""
    recommender = get_history_recommender()
    return recommender.load_cache()


# 全局调度器
_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    """获取调度器单例。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


def start_scheduler() -> None:
    """启动定时任务调度器。"""
    if not settings.history_recommend_enabled:
        logger.info("历史推荐未启用，不启动定时任务")
        return

    scheduler = get_scheduler()

    # 添加历史推荐同步任务（每天凌晨2点执行）
    # 这里简化为每24小时执行一次
    scheduler.add_task(
        name="sync_history_recommend",
        func=sync_history_recommend,
        interval_hours=settings.history_sync_interval_hours,
        run_at_start=True,  # 启动时执行一次
    )

    scheduler.start()
    logger.info("定时任务调度器已启动")


def stop_scheduler() -> None:
    """停止定时任务调度器。"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
