# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""seekdb 访问层（MySQL 协议）。

项目通过 MySQL 协议连接 seekdb 服务端（默认 ``127.0.0.1:5881``），使用服务端
的全文索引、向量索引与 AI 函数能力。每一条真实执行的 SQL 都会被记录下来，
写入 ``records/db_query_record.md``，供评审逐条核对。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import pymysql
from pymysql.cursors import DictCursor

from .config import Settings
from .sqlutil import quote_ident


class SeekDBError(RuntimeError):
    """seekdb 调用失败。"""


@dataclass
class SqlRecord:
    """一条真实执行过的 SQL 及其结果统计。"""

    step: str
    sql: str
    row_count: int = 0
    elapsed_ms: float = 0.0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "step": self.step,
            "sql": self.sql,
            "row_count": self.row_count,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "note": self.note,
        }


@dataclass
class SeekDB:
    """seekdb 连接与会话封装。"""

    settings: Settings
    connection: Any = None
    log: list[SqlRecord] = field(default_factory=list)
    _step: str = "未标注"

    # -- 生命周期 ---------------------------------------------------------
    def connect(self) -> "SeekDB":
        """建立连接（幂等）。"""
        if self.connection is not None:
            return self
        try:
            self.connection = pymysql.connect(
                host=self.settings.db_host,
                port=self.settings.db_port,
                user=self.settings.db_user,
                password=self.settings.db_password,
                charset="utf8mb4",
                autocommit=True,
                cursorclass=DictCursor,
            )
        except pymysql.Error as exc:  # pragma: no cover - 依赖外部服务
            raise SeekDBError(
                f"连接 seekdb 失败（{self.settings.db_host}:{self.settings.db_port}）：{exc}。"
                "请确认 seekdb 服务端已启动，或用 PAPERPOCKET_DB_HOST / PAPERPOCKET_DB_PORT 指定地址。"
            ) from exc
        self.use_database()
        return self

    def use_database(self) -> bool:
        """把连接的默认库切换到配置里的库。

        ``SELECT AI_COMPLETE(...)``、``INSERT INTO briefs`` 这类不带库名的语句
        需要默认库；库还不存在时（首次建库之前）返回 ``False``，不影响后续
        由建表脚本完成的 ``USE``。
        """
        try:
            self.execute(
                f"USE {quote_ident(self.settings.db_name)}",
                note="切换默认数据库",
            )
        except Exception:  # noqa: BLE001 - 库尚未创建时忽略
            return False
        return True

    def close(self) -> None:
        """关闭连接。"""
        if self.connection is not None:
            try:
                self.connection.close()
            finally:
                self.connection = None

    def __enter__(self) -> "SeekDB":
        return self.connect()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- 执行 -------------------------------------------------------------
    def step(self, name: str) -> None:
        """设置后续 SQL 的步骤名，用于记录归类。"""
        self._step = name

    def execute(self, sql: str, note: str = "") -> int:
        """执行一条写语句，返回受影响行数。"""
        self.connect()
        started = time.perf_counter()
        assert self.connection is not None
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            affected = cursor.rowcount if cursor.rowcount is not None else 0
        elapsed = (time.perf_counter() - started) * 1000
        self.log.append(
            SqlRecord(step=self._step, sql=sql, row_count=int(affected), elapsed_ms=elapsed, note=note)
        )
        return int(affected)

    def query(self, sql: str, note: str = "") -> list[dict[str, Any]]:
        """执行一条查询，返回字典列表。"""
        self.connect()
        started = time.perf_counter()
        assert self.connection is not None
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            rows = list(cursor.fetchall() or [])
        elapsed = (time.perf_counter() - started) * 1000
        self.log.append(
            SqlRecord(step=self._step, sql=sql, row_count=len(rows), elapsed_ms=elapsed, note=note)
        )
        return rows

    def script(self, statements: Sequence[str], note: str = "") -> None:
        """按顺序执行多条语句（建表、建索引等 DDL）。"""
        for statement in statements:
            text = statement.strip()
            if not text:
                continue
            self.execute(text, note=note)

    # -- 能力探测 ---------------------------------------------------------
    def server_version(self) -> str:
        """读取服务端版本号。"""
        rows = self.query("SELECT version() AS version", note="服务端版本")
        return str(rows[0]["version"]) if rows else ""

    def has_variable(self, name: str) -> bool:
        """判断当前服务端是否存在某个系统变量。"""
        rows = self.query(
            "SELECT COUNT(*) AS cnt FROM information_schema.session_variables "
            f"WHERE VARIABLE_NAME = '{name}'",
            note=f"探测系统变量 {name}",
        )
        return bool(rows and int(rows[0]["cnt"]) > 0)

    def enable_file_sql(self) -> bool:
        """尝试打开文件表能力（``read_csv`` / ``read_json`` 等）。

        文件表是赛题二的产物，并非所有 seekdb 构建都带这个能力；探测失败时
        调用方会回退到 Python 侧解析。
        """
        if not self.has_variable("enable_file_sql"):
            return False
        try:
            self.execute("SET SESSION enable_file_sql = on", note="开启文件表能力")
        except pymysql.Error:
            return False
        return True

    def indexes_of(self, table: str) -> list[dict[str, Any]]:
        """读取某张表的索引信息（用于验收脚本核对全文索引与向量索引）。

        表名带上库名，否则连接没有默认库时会报 ``No database selected``。
        """
        return self.query(
            f"SHOW INDEX FROM {quote_ident(self.settings.db_name)}.{quote_ident(table)}",
            note=f"查看 {table} 的索引",
        )

    def records_to_dicts(self) -> list[dict[str, Any]]:
        """把全部 SQL 记录转成字典列表。"""
        return [item.to_dict() for item in self.log]


def rows_to_values(rows: Iterable[dict[str, Any]], column: str) -> list[Any]:
    """从结果集中取出某一列的值列表。"""
    return [row.get(column) for row in rows]
