"""seekdb 嵌入式存储层。

工程资料（规格 / 代码符号 / 测试用例）与验证结果都存在 seekdb 里，
检索时用 SQL 直接取出参与上下文构造的行。

使用嵌入式 seekdb（pylibseekdb），无需部署数据库服务；
若设置了 ``SDDCTX_DB_DSN``，则改用 MySQL 协议连接外部 seekdb / OceanBase。
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

_ESCAPE_RE = re.compile(r"[\x00\n\r\t\x1a\"'\\]")


def quote(value: Any) -> str:
    """把 Python 值转成可直接嵌入 SQL 的字面量。

    seekdb 的 C 客户端 ``execute`` 只接受完整 SQL 字符串，没有参数占位符，
    所以所有动态值都必须在这里做转义。
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value)
    escaped = _ESCAPE_RE.sub(
        lambda m: {
            "\x00": "\\0",
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
            "\x1a": "\\Z",
            '"': '\\"',
            "'": "\\'",
            "\\": "\\\\",
        }[m.group(0)],
        text,
    )
    return f"'{escaped}'"


_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")

#: 各表的列顺序（pylibseekdb 的 Cursor 不返回列名，这里固定列顺序）。
SPEC_COLUMNS = (
    "spec_id",
    "title",
    "priority",
    "status",
    "rule",
    "acceptance",
    "source_path",
    "source_symbol",
    "source_line_start",
    "source_line_end",
    "doc_path",
    "doc_line_start",
    "doc_line_end",
)
CODE_COLUMNS = (
    "path",
    "symbol",
    "kind",
    "line_start",
    "line_end",
    "signature",
    "doc",
    "body",
)
TEST_COLUMNS = (
    "path",
    "name",
    "marker",
    "doc",
    "line_start",
    "line_end",
)
VERIFY_COLUMNS = (
    "id",
    "task_id",
    "phase",
    "suite",
    "command",
    "exit_code",
    "passed",
    "failed",
    "errored",
    "summary",
    "code_version",
    "created_at",
)
QUERY_LOG_COLUMNS = (
    "id",
    "task_id",
    "purpose",
    "sql_text",
    "row_count",
    "created_at",
)


def ident(name: str) -> str:
    """校验并返回标识符（库名、表名），拒绝非法字符。"""
    if not _IDENT_RE.match(name):
        raise ValueError(f"非法标识符: {name!r}")
    return name


class SeekdbStore:
    """工程资料与验证结果的存储与检索。"""

    def __init__(self, db_dir: str | os.PathLike[str] | None = None, database: str = "sddctx"):
        self.db_dir = Path(db_dir) if db_dir else None
        self.database = database
        self._instance = None
        self._connection = None
        self._cursor = None

    # -- 生命周期 ---------------------------------------------------------
    def open(self) -> "SeekdbStore":
        """打开数据库连接（嵌入式实例按需启动）。"""
        if self._connection is not None:
            return self
        dsn = os.environ.get("SDDCTX_DB_DSN")
        if dsn:
            self._open_mysql(dsn)
        else:
            self._open_embedded()
        self._cursor = self._connection.cursor()
        self.execute(f"CREATE DATABASE IF NOT EXISTS {ident(self.database)}")
        self.execute(f"USE {ident(self.database)}")
        return self

    def _open_embedded(self) -> None:
        import pylibseekdb

        if self.db_dir is None:
            raise ValueError("嵌入式 seekdb 需要 db_dir，或设置 SDDCTX_DB_DSN 使用外部实例")
        self.db_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._instance = pylibseekdb.open(db_dir=str(self.db_dir))
        except Exception as exc:  # noqa: BLE001 - 转成可读提示后原样抛出
            raise RuntimeError(
                f"无法打开嵌入式 seekdb 数据库目录 {self.db_dir}：{exc}\n"
                "嵌入式 seekdb 底层使用 O_DIRECT 直写，数据目录必须位于支持 "
                "O_DIRECT 的**本地文件系统**上（NFS 等网络文件系统会报 "
                "seekdb_open failed: code=-1）。\n"
                "请用环境变量 SDDCTX_HOME 指定一个本地路径后重试，"
                "例如：SDDCTX_HOME=/var/tmp/sddctx-runtime"
            ) from exc
        # 嵌入式实例自带的 test 库一定存在，先连上去再建目标库。
        self._connection = pylibseekdb.connect(database="test")

    def _open_mysql(self, dsn: str) -> None:
        import pymysql

        params = _parse_dsn(dsn)
        database = params.pop("database")
        self._connection = pymysql.connect(**params, autocommit=False)
        self._connection.cursor().execute(
            f"CREATE DATABASE IF NOT EXISTS {quote(database)}"
        )
        self._connection.commit()

    def close(self) -> None:
        """关闭连接。"""
        if self._connection is not None:
            try:
                self._connection.commit()
            except Exception:  # noqa: BLE001 - 关闭阶段忽略底层异常
                pass
            try:
                self._connection.close()
            except Exception:  # noqa: BLE001
                pass
            self._connection = None
        if self._instance is not None:
            try:
                self._instance.close()
            except Exception:  # noqa: BLE001
                pass
            self._instance = None
        self._cursor = None

    def __enter__(self) -> "SeekdbStore":
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- 基础操作 ---------------------------------------------------------
    def execute(self, sql: str) -> int:
        """执行一条 SQL。"""
        if self._cursor is None:
            raise RuntimeError("数据库尚未打开，请先调用 open()")
        self._cursor.execute(sql)
        return int(getattr(self._cursor, "rowcount", 0) or 0)

    def query(self, sql: str, columns: Sequence[str]) -> list[dict[str, Any]]:
        """执行查询并返回字典列表。

        pylibseekdb 的 Cursor 只有 execute/fetchall，没有 description，
        所以列名必须由调用方给出，并与 SELECT 列表保持一致。
        """
        if self._cursor is None:
            raise RuntimeError("数据库尚未打开，请先调用 open()")
        self._cursor.execute(sql)
        rows = self._cursor.fetchall() or []
        return [dict(zip(columns, row)) for row in rows]

    def commit(self) -> None:
        if self._connection is not None:
            self._connection.commit()

    # -- 表结构 -----------------------------------------------------------
    def create_schema(self) -> None:
        """建表并建立全文索引。"""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS spec_entry (
                spec_id VARCHAR(64) NOT NULL PRIMARY KEY,
                title VARCHAR(256) NOT NULL,
                priority VARCHAR(16) NOT NULL,
                status VARCHAR(32) NOT NULL,
                rule TEXT NOT NULL,
                acceptance TEXT NOT NULL,
                source_path VARCHAR(512) NOT NULL,
                source_symbol VARCHAR(128) NOT NULL,
                source_line_start INT NOT NULL,
                source_line_end INT NOT NULL,
                doc_path VARCHAR(512) NOT NULL,
                doc_line_start INT NOT NULL,
                doc_line_end INT NOT NULL,
                updated_at VARCHAR(32) NOT NULL,
                FULLTEXT INDEX ft_spec (title, rule) WITH PARSER ngram
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS code_symbol (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                path VARCHAR(512) NOT NULL,
                symbol VARCHAR(160) NOT NULL,
                kind VARCHAR(32) NOT NULL,
                line_start INT NOT NULL,
                line_end INT NOT NULL,
                signature VARCHAR(512) NOT NULL,
                doc TEXT NOT NULL,
                body MEDIUMTEXT NOT NULL,
                UNIQUE KEY uk_code_symbol (path, symbol, line_start),
                FULLTEXT INDEX ft_code (symbol, signature, doc) WITH PARSER ngram
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS test_case (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                path VARCHAR(512) NOT NULL,
                name VARCHAR(256) NOT NULL,
                marker VARCHAR(32) NOT NULL,
                doc TEXT NOT NULL,
                line_start INT NOT NULL,
                line_end INT NOT NULL,
                UNIQUE KEY uk_test_case (path, name),
                FULLTEXT INDEX ft_test (name, doc) WITH PARSER ngram
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS verification_result (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                task_id VARCHAR(128) NOT NULL,
                phase VARCHAR(32) NOT NULL,
                suite VARCHAR(64) NOT NULL,
                command TEXT NOT NULL,
                exit_code INT NOT NULL,
                passed INT NOT NULL,
                failed INT NOT NULL,
                errored INT NOT NULL,
                summary VARCHAR(512) NOT NULL,
                code_version VARCHAR(128) NOT NULL,
                created_at VARCHAR(32) NOT NULL,
                KEY idx_verify_task (task_id, phase)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS query_log (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                task_id VARCHAR(128) NOT NULL,
                purpose VARCHAR(64) NOT NULL,
                sql_text TEXT NOT NULL,
                row_count INT NOT NULL,
                created_at VARCHAR(32) NOT NULL
            )
            """,
        ]
        for statement in statements:
            self.execute(statement)
        self.commit()

    # -- 写入 -------------------------------------------------------------
    def upsert_spec(self, row: dict[str, Any]) -> None:
        """写入（覆盖）一条规格条目。"""
        columns = [
            "spec_id",
            "title",
            "priority",
            "status",
            "rule",
            "acceptance",
            "source_path",
            "source_symbol",
            "source_line_start",
            "source_line_end",
            "doc_path",
            "doc_line_start",
            "doc_line_end",
            "updated_at",
        ]
        values = ", ".join(quote(row.get(column)) for column in columns)
        self.execute(f"REPLACE INTO spec_entry ({', '.join(columns)}) VALUES ({values})")

    def replace_code_symbols(self, rows: Sequence[dict[str, Any]]) -> None:
        """整体替换代码符号表，保证与磁盘现状一致。"""
        self.execute("DELETE FROM code_symbol")
        for row in rows:
            self.execute(
                "INSERT INTO code_symbol (path, symbol, kind, line_start, line_end, signature, doc, body) "
                f"VALUES ({quote(row['path'])}, {quote(row['symbol'])}, {quote(row['kind'])}, "
                f"{int(row['line_start'])}, {int(row['line_end'])}, {quote(row['signature'])}, "
                f"{quote(row['doc'])}, {quote(row['body'])})"
            )

    def replace_test_cases(self, rows: Sequence[dict[str, Any]]) -> None:
        """整体替换测试用例表。"""
        self.execute("DELETE FROM test_case")
        for row in rows:
            self.execute(
                "INSERT INTO test_case (path, name, marker, doc, line_start, line_end) "
                f"VALUES ({quote(row['path'])}, {quote(row['name'])}, {quote(row['marker'])}, "
                f"{quote(row['doc'])}, {int(row['line_start'])}, {int(row['line_end'])})"
            )

    def insert_verification(self, row: dict[str, Any]) -> None:
        """写入一条验证结果。"""
        self.execute(
            "INSERT INTO verification_result (task_id, phase, suite, command, exit_code, passed, failed, "
            "errored, summary, code_version, created_at) VALUES ("
            f"{quote(row['task_id'])}, {quote(row['phase'])}, {quote(row['suite'])}, {quote(row['command'])}, "
            f"{int(row['exit_code'])}, {int(row['passed'])}, {int(row['failed'])}, {int(row['errored'])}, "
            f"{quote(row['summary'])}, {quote(row['code_version'])}, {quote(row['created_at'])})"
        )

    def insert_query_log(self, task_id: str, purpose: str, sql_text: str, row_count: int, created_at: str) -> None:
        """记录一次用于构造上下文的数据库查询。"""
        self.execute(
            "INSERT INTO query_log (task_id, purpose, sql_text, row_count, created_at) VALUES ("
            f"{quote(task_id)}, {quote(purpose)}, {quote(sql_text)}, {int(row_count)}, {quote(created_at)})"
        )

    # -- 查询 -------------------------------------------------------------
    def fetch_specs(self, spec_ids: Iterable[str]) -> list[dict[str, Any]]:
        """按编号取规格条目。"""
        ids = list(spec_ids)
        if not ids:
            return []
        clause = ", ".join(quote(item) for item in ids)
        return self.query(
            f"SELECT {', '.join(SPEC_COLUMNS)} FROM spec_entry WHERE spec_id IN ({clause}) ORDER BY spec_id",
            SPEC_COLUMNS,
        )

    def fetch_symbols_by_path(self, paths: Iterable[str]) -> list[dict[str, Any]]:
        """按文件路径取代码符号。"""
        items = list(paths)
        if not items:
            return []
        clause = ", ".join(quote(item) for item in items)
        return self.query(
            f"SELECT {', '.join(CODE_COLUMNS)} FROM code_symbol WHERE path IN ({clause}) ORDER BY path, line_start",
            CODE_COLUMNS,
        )

    def fetch_tests_by_path(self, paths: Iterable[str]) -> list[dict[str, Any]]:
        """按文件路径取测试用例。"""
        items = list(paths)
        if not items:
            return []
        clause = ", ".join(quote(item) for item in items)
        return self.query(
            f"SELECT {', '.join(TEST_COLUMNS)} FROM test_case WHERE path IN ({clause}) ORDER BY path, line_start",
            TEST_COLUMNS,
        )

    def fetch_verifications(self, task_id: str) -> list[dict[str, Any]]:
        """取某个任务的全部验证结果。"""
        return self.query(
            f"SELECT {', '.join(VERIFY_COLUMNS)} FROM verification_result "
            f"WHERE task_id = {quote(task_id)} ORDER BY id",
            VERIFY_COLUMNS,
        )

    def fetch_query_log(self, task_id: str | None = None) -> list[dict[str, Any]]:
        """取数据库查询日志。"""
        if task_id:
            return self.query(
                f"SELECT {', '.join(QUERY_LOG_COLUMNS)} FROM query_log WHERE task_id = {quote(task_id)} ORDER BY id",
                QUERY_LOG_COLUMNS,
            )
        return self.query(
            f"SELECT {', '.join(QUERY_LOG_COLUMNS)} FROM query_log ORDER BY id",
            QUERY_LOG_COLUMNS,
        )


@contextmanager
def open_store(db_dir: str | os.PathLike[str] | None, database: str = "sddctx") -> Iterator[SeekdbStore]:
    """打开存储的上下文管理器。"""
    store = SeekdbStore(db_dir=db_dir, database=database)
    try:
        yield store.open()
    finally:
        store.close()


def _parse_dsn(dsn: str) -> dict[str, Any]:
    """解析 ``mysql://user:password@host:port/db`` 形式的 DSN。"""
    from urllib.parse import unquote, urlparse

    parsed = urlparse(dsn)
    params: dict[str, Any] = {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 2881,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": (parsed.path or "/test").lstrip("/") or "test",
        "charset": "utf8mb4",
    }
    return params
