"""日志配置模块，支持日志轮转和清理。"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings


def setup_logging(
    app_name: str = "app",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """配置日志轮转。

    Args:
        app_name: 应用名称，用于日志文件名
        level: 日志级别，默认 INFO
        max_bytes: 单个日志文件最大大小，默认 10MB
        backup_count: 保留的日志文件数量，默认 5 个
    """
    # 日志目录
    log_dir = settings.root_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 日志文件路径
    log_file = log_dir / f"{app_name}.log"

    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # 文件输出（轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取日志器。

    Args:
        name: 日志器名称

    Returns:
        logging.Logger: 日志器实例
    """
    return logging.getLogger(name)