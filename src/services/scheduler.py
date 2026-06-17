"""定时任务调度器。

负责定时同步历史推荐统计数据。
支持两种调度模式：
1. 间隔模式：按指定时间间隔执行（如每24小时）
2. 定时模式：每天指定时间执行（如每天凌晨1点）
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
        """添加定时任务（间隔模式）。"""
        self._tasks.append({
            "name": name,
            "func": func,
            "interval_hours": interval_hours,
            "run_at_start": run_at_start,
            "last_run": None,
            "mode": "interval",
        })

    def add_daily_task(
        self,
        name: str,
        func: Callable,
        run_at_time: str = "01:00",
        run_at_start: bool = False,
    ) -> None:
        """添加定时任务（每天指定时间执行）。

        Args:
            name: 任务名称
            func: 任务函数
            run_at_time: 执行时间，格式 "HH:MM"（如 "01:00" 表示凌晨1点）
            run_at_start: 启动时是否立即执行一次
        """
        self._tasks.append({
            "name": name,
            "func": func,
            "run_at_time": run_at_time,
            "run_at_start": run_at_start,
            "last_run": None,
            "mode": "daily",
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

    def _should_run_task(self, task: dict, now: datetime) -> bool:
        """判断任务是否应该执行。"""
        last_run = task["last_run"]
        mode = task.get("mode", "interval")

        if mode == "daily":
            # 定时模式：每天指定时间执行
            run_at_time = task.get("run_at_time", "01:00")
            target_hour, target_minute = map(int, run_at_time.split(":"))

            # 判断当前时间是否在目标时间的前一分钟内（避免漏掉）
            if now.hour == target_hour and now.minute == 0:
                # 如果今天还没执行过，或者上次执行不是今天
                if last_run is None or last_run.date() != now.date():
                    return True
            return False
        else:
            # 间隔模式：按指定时间间隔执行
            interval = timedelta(hours=task.get("interval_hours", 24))
            if last_run is None or (now - last_run) >= interval:
                return True
            return False

    def _scheduler_loop(self) -> None:
        """调度循环。"""
        logger.info("定时任务调度器启动")

        # 启动时执行标记了 run_at_start 的任务
        for task in self._tasks:
            if task.get("run_at_start"):
                self._run_task(task)

        while self._running:
            now = datetime.now()

            for task in self._tasks:
                if self._should_run_task(task, now):
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

    优先从 rucp_task_process（position=fast_handle）同步，
    同时从 rucp_element_mapping_history 同步历史对标记录。

    Args:
        force_full: 是否强制全量同步
    """
    sync_service = get_sync_service()

    # 从 task_process 表同步人工对标结果
    result = sync_service.sync_from_task_process(force_full=force_full)

    # 同时从历史对标记录表同步（如存在）
    history_result = sync_service.sync_from_history(force_full=force_full)

    # 合并结果
    if result.get("status") == "success" or history_result.get("status") == "success":
        recommender = get_history_recommender()
        recommender.load_cache()

    # 返回 task_process 的结果为主，附带 history 结果
    result["history_sync"] = history_result
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

    # 添加历史推荐同步任务（每天凌晨1点执行）
    scheduler.add_daily_task(
        name="sync_history_recommend",
        func=sync_history_recommend,
        run_at_time=settings.history_sync_run_at_time,
        run_at_start=True,  # 启动时执行一次
    )

    scheduler.start()
    logger.info("定时任务调度器已启动")


def stop_scheduler() -> None:
    """停止定时任务调度器。"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
