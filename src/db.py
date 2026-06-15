"""数据库连接模块。"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

import pymysql
from pymysql.cursors import DictCursor

from config import settings

logger = logging.getLogger(__name__)


def get_connection() -> pymysql.Connection:
    """获取主数据库连接。"""
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset=settings.db_charset,
        cursorclass=DictCursor,
    )


def get_history_connection() -> pymysql.Connection:
    """获取历史推荐数据库连接。"""
    return pymysql.connect(
        host=settings.history_db_host,
        port=settings.history_db_port,
        user=settings.history_db_user,
        password=settings.history_db_password,
        database=settings.history_db_name,
        charset=settings.history_db_charset,
        cursorclass=DictCursor,
    )


@contextmanager
def get_cursor() -> Generator[DictCursor, None, None]:
    """获取主数据库游标上下文管理器。"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"数据库操作失败: {e}")
        raise
    finally:
        conn.close()


@contextmanager
def get_history_cursor() -> Generator[DictCursor, None, None]:
    """获取历史数据库游标上下文管理器。"""
    conn = get_history_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"历史数据库操作失败: {e}")
        raise
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """查询所有记录（主数据库）。"""
    with get_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """查询单条记录（主数据库）。"""
    with get_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """执行SQL语句（主数据库），返回影响行数。"""
    with get_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


# ========== 历史数据库操作 ==========

def history_query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """查询所有记录（历史数据库）。"""
    with get_history_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def history_query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """查询单条记录（历史数据库）。"""
    with get_history_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def history_execute(sql: str, params: tuple = ()) -> int:
    """执行SQL语句（历史数据库），返回影响行数。"""
    with get_history_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


# ========== 人工对标过程数据库操作（与历史库同库） ==========

def task_process_query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """查询所有记录（与历史库同库）。"""
    with get_history_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()
