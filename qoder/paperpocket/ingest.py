"""资料导入：把论文与笔记写入 seekdb。

导入过程会做三件事：

1. 写入 ``papers`` 表（文档级元数据 + 全文 + 向量）；
2. 按标题层级把正文切成段落块，写入 ``paper_chunks`` 表（带来源路径与行号）；
3. 在 ``reading_log`` 表里留下导入记录。

向量有两种来源：``local``（本地确定性哈希嵌入，写入字面量）与 ``ai``
（由 seekdb 内部执行 ``AI_EMBED('<模型>', '<文本>')`` 计算并写入）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .brief import extractive_summary
from .corpus import Chunk, Document, chunk_document
from .db import SeekDB
from .embedding import Embedder
from .sqlutil import sql_int, sql_str, sql_vector


@dataclass
class IngestReport:
    """一次导入的结果统计。"""

    documents: int = 0
    chunks: int = 0
    deleted: int = 0
    embed_mode: str = "local"
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "documents": self.documents,
            "chunks": self.chunks,
            "deleted": self.deleted,
            "embed_mode": self.embed_mode,
            "details": self.details,
        }


class Ingestor:
    """资料导入器。"""

    def __init__(self, db: SeekDB, embedder: Embedder, db_name: str) -> None:
        self.db = db
        self.embedder = embedder
        self.db_name = db_name

    # -- 单条写入 ---------------------------------------------------------
    def _vector_expression(self, text: str) -> str:
        """返回向量表达式（AI 通道返回 ``AI_EMBED(...)``，本地通道返回字面量）。"""
        return self.embedder.embed_expression(text)

    def _insert_paper(self, document: Document) -> None:
        """写入一篇论文。"""
        summary = extractive_summary([document.content], document.title, max_points=3)
        vector = self._vector_expression(f"{document.title}\n{document.content[:1200]}")
        sql = (
            "INSERT INTO papers (doc_key, title, authors, year, venue, tags, kind, source_path, "
            f"summary, content, emb) VALUES ({sql_str(document.doc_key)}, {sql_str(document.title)}, "
            f"{sql_str(document.authors)}, {sql_int(document.year)}, {sql_str(document.venue)}, "
            f"{sql_str(document.tags_text)}, {sql_str(document.kind)}, {sql_str(document.source_path)}, "
            f"{sql_str(summary)}, {sql_str(document.content)}, {vector})"
        )
        self.db.execute(sql, note=f"写入论文 {document.doc_key}")

    def _insert_chunk(self, chunk: Chunk) -> None:
        """写入一个段落块。"""
        vector = self._vector_expression(f"{chunk.heading}\n{chunk.content}")
        sql = (
            "INSERT INTO paper_chunks (chunk_key, doc_key, title, authors, year, venue, tags, heading, "
            f"seq, source_path, start_line, end_line, content, emb) VALUES ({sql_str(chunk.chunk_key)}, "
            f"{sql_str(chunk.doc_key)}, {sql_str(chunk.title)}, {sql_str(chunk.authors)}, "
            f"{sql_int(chunk.year)}, {sql_str(chunk.venue)}, {sql_str(chunk.tags_text)}, "
            f"{sql_str(chunk.heading)}, {sql_int(chunk.seq)}, {sql_str(chunk.source_path)}, "
            f"{sql_int(chunk.start_line)}, {sql_int(chunk.end_line)}, {sql_str(chunk.content)}, {vector})"
        )
        self.db.execute(sql, note=f"写入段落 {chunk.chunk_key}")

    def _log(self, doc_key: str, action: str, detail: str) -> None:
        """写入一条日志。"""
        sql = (
            "INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES "
            f"({sql_str(doc_key)}, '', {sql_str(action)}, '', 0, {sql_str(detail)})"
        )
        self.db.execute(sql, note=f"记录日志 {action}")

    # -- 主流程 -----------------------------------------------------------
    def ingest_documents(self, documents: list[Document], max_chars: int = 480) -> IngestReport:
        """导入一批资料（幂等：同一 ``doc_key`` 先删后写）。"""
        report = IngestReport(embed_mode="ai" if self.embedder.ai_available() else "local")
        self.db.step("导入资料")
        for document in documents:
            deleted = self.db.execute(
                f"DELETE FROM paper_chunks WHERE doc_key = {sql_str(document.doc_key)}",
                note=f"清理旧段落 {document.doc_key}",
            )
            report.deleted += deleted
            self.db.execute(
                f"DELETE FROM papers WHERE doc_key = {sql_str(document.doc_key)}",
                note=f"清理旧论文 {document.doc_key}",
            )
            self._insert_paper(document)
            chunks = chunk_document(document, max_chars=max_chars)
            for chunk in chunks:
                self._insert_chunk(chunk)
            report.documents += 1
            report.chunks += len(chunks)
            self._log(document.doc_key, "ingest", f"导入 {len(chunks)} 个段落")
            report.details.append(
                {
                    "doc_key": document.doc_key,
                    "title": document.title,
                    "year": document.year,
                    "tags": document.tags,
                    "chunks": len(chunks),
                    "source_path": document.source_path,
                }
            )
        return report
