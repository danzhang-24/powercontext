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
"""seekdb 表结构、全文索引与向量索引。

设计要点：

1. ``papers`` 与 ``paper_chunks`` **不声明用户主键**，只用唯一索引约束自然键。
   这样 seekdb 使用隐藏主键（``__pk_increment``），服务端原生混合检索
   ``dbms_hybrid_search`` 才能在这两张表上工作（该接口不支持带用户主键的表）。
2. ``paper_chunks`` 上建立 **全文索引**（``title`` + ``content``，ngram 解析器，
   中文按二元组切分）与 **向量索引**（``emb`` 列，HNSW + vsag，L2 距离）。
3. ``reading_log`` 与 ``briefs`` 记录检索历史与简报，带自增主键即可。
"""

from __future__ import annotations

from .db import SeekDB
from .sqlutil import quote_ident

#: 参与检索的表名。
PAPERS_TABLE = "papers"
CHUNKS_TABLE = "paper_chunks"
LOG_TABLE = "reading_log"
BRIEFS_TABLE = "briefs"


def table_ddl(db_name: str, embed_dim: int) -> list[str]:
    """返回建库与建表语句。"""
    return [
        f"CREATE DATABASE IF NOT EXISTS {quote_ident(db_name)}",
        f"USE {quote_ident(db_name)}",
        f"""
        CREATE TABLE IF NOT EXISTS {PAPERS_TABLE} (
            doc_key VARCHAR(96) NOT NULL,
            title VARCHAR(512) NOT NULL,
            authors VARCHAR(512) NOT NULL DEFAULT '',
            year INT NOT NULL DEFAULT 0,
            venue VARCHAR(256) NOT NULL DEFAULT '',
            tags VARCHAR(256) NOT NULL DEFAULT '',
            kind VARCHAR(32) NOT NULL DEFAULT 'paper',
            source_path VARCHAR(512) NOT NULL DEFAULT '',
            summary MEDIUMTEXT,
            content MEDIUMTEXT NOT NULL,
            emb VECTOR({embed_dim}),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CHUNKS_TABLE} (
            chunk_key VARCHAR(128) NOT NULL,
            doc_key VARCHAR(96) NOT NULL,
            title VARCHAR(512) NOT NULL,
            authors VARCHAR(512) NOT NULL DEFAULT '',
            year INT NOT NULL DEFAULT 0,
            venue VARCHAR(256) NOT NULL DEFAULT '',
            tags VARCHAR(256) NOT NULL DEFAULT '',
            heading VARCHAR(256) NOT NULL DEFAULT '',
            seq INT NOT NULL DEFAULT 0,
            source_path VARCHAR(512) NOT NULL DEFAULT '',
            start_line INT NOT NULL DEFAULT 0,
            end_line INT NOT NULL DEFAULT 0,
            content MEDIUMTEXT NOT NULL,
            emb VECTOR({embed_dim}),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
            id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            doc_key VARCHAR(96) NOT NULL DEFAULT '',
            chunk_key VARCHAR(128) NOT NULL DEFAULT '',
            action VARCHAR(32) NOT NULL,
            query_text VARCHAR(512) NOT NULL DEFAULT '',
            score DOUBLE NOT NULL DEFAULT 0,
            detail TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {BRIEFS_TABLE} (
            id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            query_text VARCHAR(512) NOT NULL,
            brief_md MEDIUMTEXT NOT NULL,
            engine VARCHAR(32) NOT NULL,
            model_name VARCHAR(64) NOT NULL DEFAULT '',
            source_keys TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]


def index_ddl(embed_dim: int) -> list[tuple[str, str, str]]:
    """返回索引语句列表（全文索引 + 向量索引 + 唯一索引）。

    每项是 ``(表名, 索引名, 语句)``——索引名用于在创建前判断索引是否已存在。
    """
    return [
        (PAPERS_TABLE, "uk_papers_doc", f"CREATE UNIQUE INDEX uk_papers_doc ON {PAPERS_TABLE} (doc_key)"),
        (CHUNKS_TABLE, "uk_chunks_key", f"CREATE UNIQUE INDEX uk_chunks_key ON {CHUNKS_TABLE} (chunk_key)"),
        (CHUNKS_TABLE, "idx_chunks_doc", f"CREATE INDEX idx_chunks_doc ON {CHUNKS_TABLE} (doc_key)"),
        (CHUNKS_TABLE, "idx_chunks_year", f"CREATE INDEX idx_chunks_year ON {CHUNKS_TABLE} (year)"),
        (
            PAPERS_TABLE,
            "ft_papers",
            f"CREATE FULLTEXT INDEX ft_papers ON {PAPERS_TABLE} (title, content) WITH PARSER ngram",
        ),
        (
            CHUNKS_TABLE,
            "ft_chunks",
            f"CREATE FULLTEXT INDEX ft_chunks ON {CHUNKS_TABLE} (title, content) WITH PARSER ngram",
        ),
        (
            PAPERS_TABLE,
            "vi_papers",
            f"CREATE VECTOR INDEX vi_papers ON {PAPERS_TABLE} (emb) "
            "WITH (distance=l2, type=hnsw, lib=vsag)",
        ),
        (
            CHUNKS_TABLE,
            "vi_chunks",
            f"CREATE VECTOR INDEX vi_chunks ON {CHUNKS_TABLE} (emb) "
            "WITH (distance=l2, type=hnsw, lib=vsag)",
        ),
    ]


def prepare(db: SeekDB, db_name: str, embed_dim: int) -> None:
    """建库、建表并补齐索引（幂等：已存在的对象跳过）。

    seekdb 对"重复创建向量索引"报的是 1235（``create vector index on column
    has vector index is not supported``），而不是"already exist"，因此这里先用
    ``SHOW INDEX`` 判断索引名是否已经存在，避免第二次运行时直接失败。
    """
    db.step("建库建表")
    db.script(table_ddl(db_name, embed_dim), note="建库建表")
    db.step("建索引")
    existing: dict[str, set[str]] = {}
    for table, name, statement in index_ddl(embed_dim):
        if table not in existing:
            existing[table] = {
                str(row.get("Key_name") or "") for row in db.indexes_of(table)
            }
        if name in existing[table]:
            continue
        try:
            db.execute(statement, note="建索引")
        except Exception as exc:  # noqa: BLE001 - 索引可能已存在
            message = str(exc)
            if "already exist" in message.lower() or "duplicate" in message.lower():
                continue
            raise


def drop_all(db: SeekDB, db_name: str) -> None:
    """删除整个库（用于 ``reset`` 子命令）。"""
    db.step("重置数据库")
    db.execute(f"DROP DATABASE IF EXISTS {quote_ident(db_name)}", note="删除数据库")


def table_counts(db: SeekDB, db_name: str) -> dict[str, int]:
    """统计各表行数。"""
    counts: dict[str, int] = {}
    for table in (PAPERS_TABLE, CHUNKS_TABLE, LOG_TABLE, BRIEFS_TABLE):
        rows = db.query(
            f"SELECT COUNT(*) AS cnt FROM {quote_ident(db_name)}.{quote_ident(table)}",
            note=f"统计 {table} 行数",
        )
        counts[table] = int(rows[0]["cnt"]) if rows else 0
    return counts
