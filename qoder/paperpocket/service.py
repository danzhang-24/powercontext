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
"""应用门面：把 seekdb、PowerContext 与检索 / 简报能力组装起来。

CLI 与演示脚本都通过 :class:`PaperPocket` 访问功能，保证：
数据库连接、记忆读写、记录收集的行为在任何入口下都一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .brief import BriefGenerator, BriefResult
from .config import Settings
from .corpus import iter_documents
from .db import SeekDB
from .embedding import Embedder
from .ingest import IngestReport, Ingestor
from .memory import MemoryProfile, MemorySnapshot, MemoryStore
from .records import MemoryRead as MemoryReadRecord
from .records import MemoryWrite as MemoryWriteRecord
from .retrieval import HybridSearch, SearchFilters, SearchResult
from .schema import prepare, table_counts


@dataclass
class PaperPocket:
    """PaperPocket 应用门面。"""

    settings: Settings
    db: SeekDB = field(init=False)
    embedder: Embedder = field(init=False)
    memory: MemoryStore = field(init=False)
    searcher: HybridSearch = field(init=False)
    brief: BriefGenerator = field(init=False)
    memory_writes: list[MemoryWriteRecord] = field(default_factory=list)
    memory_reads: list[MemoryReadRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        """构造各子组件。"""
        self.settings.ensure_dirs()
        self.db = SeekDB(self.settings)
        self.embedder = Embedder(
            db=self.db,
            dim=self.settings.embed_dim,
            mode=self.settings.embed_mode,
            model=self.settings.embed_model,
        )
        self.memory = MemoryStore(
            base_url=self.settings.powercontext_url,
            scope_id=self.settings.scope_id,
            binding_path=self.settings.scope_binding_path,
        )
        self.searcher = HybridSearch(self.db, self.embedder, self.settings.db_name)
        self.brief = BriefGenerator(self.db, model=self.settings.complete_model)

    # -- 生命周期 ---------------------------------------------------------
    def open(self) -> "PaperPocket":
        """连接数据库。"""
        self.db.connect()
        return self

    def close(self) -> None:
        """关闭数据库连接。"""
        self.db.close()

    def __enter__(self) -> "PaperPocket":
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- 记忆辅助 ---------------------------------------------------------
    def _track_write(self, entry_type: str, reason: str, text: str, response: dict[str, Any]) -> None:
        """记录一次 PowerContext 写入。"""
        citation = response.get("entry") or {}
        entry_id = ""
        if isinstance(citation, dict):
            entry_id = str((citation.get("citation") or {}).get("entry_id") or "")
        revision = int(response.get("version") or 0)
        self.memory_writes.append(
            MemoryWriteRecord(
                entry_type=entry_type,
                reason=reason,
                text=text,
                scope_id=self.memory.ensure_scope(),
                entry_id=entry_id,
                revision=revision,
                response=response,
            )
        )

    def _track_read(self, query: str, hits: list[dict[str, Any]]) -> None:
        """记录一次 PowerContext 读回。"""
        self.memory_reads.append(
            MemoryReadRecord(
                query=query,
                scope_id=self.memory.ensure_scope(),
                hits=[{"text": hit.get("text"), "score": hit.get("score")} for hit in hits],
            )
        )

    def load_memory(self, track: bool = True) -> MemorySnapshot:
        """读回记忆快照（并记录到技术使用记录）。"""
        scope_id = self.memory.ensure_scope()
        hits = self.memory.search_memories("paperpocket", limit=100)
        if track:
            self._track_read("paperpocket", hits)
        snapshot = self.memory.load(limit=100)
        snapshot.scope_id = scope_id
        return snapshot

    def remember_profile(self, direction: str, tags: list[str]) -> dict[str, Any]:
        """记住研究方向与标签。"""
        response = self.memory.remember_profile(direction, tags)
        self._track_write("profile", f"记住研究方向：{direction}", response.get("text", ""), response)
        return response

    def remember_query(self, query: str, top_keys: list[str]) -> dict[str, Any]:
        """记住一次检索。"""
        response = self.memory.remember_query(query, top_keys)
        self._track_write("history", f"记住检索历史：{query}", response.get("text", ""), response)
        return response

    def remember_progress(self, doc_key: str, title: str, status: str = "read") -> dict[str, Any]:
        """记住阅读进度。"""
        response = self.memory.remember_progress(doc_key, title, status)
        self._track_write("progress", f"记住阅读进度：{title}", response.get("text", ""), response)
        return response

    # -- 功能 -------------------------------------------------------------
    def prepare_schema(self) -> None:
        """建库、建表并创建全文索引与向量索引。"""
        prepare(self.db, self.settings.db_name, self.settings.embed_dim)

    def setup_ai_models(self) -> dict[str, Any]:
        """把本地模型服务注册到 seekdb，使 ``AI_EMBED`` / ``AI_COMPLETE`` 可用。

        注册完成后，seekdb 在执行 ``AI_EMBED('pp_embed', '...')`` 时会自己去请求
        模型端点——向量的计算发生在数据库内部，而不是在 Python 侧。

        服务端不支持 AI 服务（缺少 ``DBMS_AI_SERVICE``）时返回失败信息，调用方
        会退回到本地确定性嵌入，功能不受影响。
        """
        base = self.settings.model_server_base
        embedding_url = f"{base}/v1/embeddings"
        completion_url = f"{base}/v1/chat/completions"
        results: dict[str, Any] = {"embedding_model": None, "completion_model": None, "errors": []}

        def run(sql: str, label: str) -> None:
            try:
                self.db.execute(sql, note=label)
            except Exception as exc:  # noqa: BLE001 - 兼容没有 AI 服务的构建
                results["errors"].append(f"{label}：{exc}")

        for name in (self.settings.embed_model, self.settings.complete_model):
            run(f"CALL DBMS_AI_SERVICE.DROP_AI_MODEL('{name}')", f"删除旧模型 {name}")
            run(f"CALL DBMS_AI_SERVICE.DROP_AI_MODEL_ENDPOINT('{name}')", f"删除旧端点 {name}")

        embed_model = self.settings.embed_model
        complete_model = self.settings.complete_model
        run(
            "CALL DBMS_AI_SERVICE.CREATE_AI_MODEL('"
            + embed_model
            + "', '{\"type\":\"DENSE_EMBEDDING\",\"model_name\":\"paperpocket-local\"}')",
            f"注册嵌入模型 {embed_model}",
        )
        run(
            "CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT('"
            + embed_model
            + "', '{\"ai_model_name\":\""
            + embed_model
            + "\",\"url\":\""
            + embedding_url
            + "\",\"access_key\":\"local\",\"provider\":\"openai\","
            "\"request_model_name\":\"paperpocket-local\"}')",
            f"注册嵌入端点 {embed_model}",
        )
        run(
            "CALL DBMS_AI_SERVICE.CREATE_AI_MODEL('"
            + complete_model
            + "', '{\"type\":\"COMPLETION\",\"model_name\":\"paperpocket-local\"}')",
            f"注册摘要模型 {complete_model}",
        )
        run(
            "CALL DBMS_AI_SERVICE.CREATE_AI_MODEL_ENDPOINT('"
            + complete_model
            + "', '{\"ai_model_name\":\""
            + complete_model
            + "\",\"url\":\""
            + completion_url
            + "\",\"access_key\":\"local\",\"provider\":\"openai\","
            "\"request_model_name\":\"paperpocket-local\"}')",
            f"注册摘要端点 {complete_model}",
        )

        results["embedding_model"] = embed_model if self.embedder.ai_available() else None
        results["completion_model"] = complete_model if self.brief.model_available() else None
        results["embedding_url"] = embedding_url
        results["completion_url"] = completion_url
        return results

    def ingest(self, corpus_dir: Path | None = None, max_chars: int = 480) -> IngestReport:
        """导入语料目录下的资料。"""
        directory = corpus_dir or self.settings.corpus_dir
        documents = iter_documents(directory)
        ingestor = Ingestor(self.db, self.embedder, self.settings.db_name)
        return ingestor.ingest_documents(documents, max_chars=max_chars)

    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        top_k: int = 8,
        use_memory: bool = True,
        remember: bool = True,
        candidate_limit: int = 40,
    ) -> SearchResult:
        """执行一次混合检索（可选读取并写回记忆）。"""
        snapshot = self.load_memory() if use_memory else MemorySnapshot()
        result = self.searcher.search(
            query,
            filters=filters,
            top_k=top_k,
            candidate_limit=candidate_limit,
            snapshot=snapshot if use_memory else None,
            use_memory=use_memory,
        )
        if remember:
            self.remember_query(query, [hit.chunk_key for hit in result.hits[:5]])
        return result

    def make_brief(
        self,
        query: str,
        filters: SearchFilters | None = None,
        top_k: int = 6,
        use_memory: bool = True,
        use_ai: bool = True,
        remember: bool = True,
    ) -> tuple[SearchResult, BriefResult]:
        """检索并生成简报。"""
        result = self.search(
            query,
            filters=filters,
            top_k=top_k,
            use_memory=use_memory,
            remember=remember,
        )
        brief = self.brief.generate(query, result.hits, use_ai=use_ai)
        self.db.step("保存简报")
        source_keys = ",".join(hit.chunk_key for hit in result.hits)
        self.db.execute(
            "INSERT INTO briefs (query_text, brief_md, engine, model_name, source_keys) VALUES ("
            f"{sql_str_text(query)}, {sql_str_text(brief.text)}, {sql_str_text(brief.engine)}, "
            f"{sql_str_text(brief.model)}, {sql_str_text(source_keys)})",
            note="保存简报",
        )
        for hit in result.hits[:2]:
            self.db.step("记录简报来源")
            self.db.execute(
                "INSERT INTO reading_log (doc_key, chunk_key, action, query_text, score, detail) VALUES ("
                f"{sql_str_text(hit.doc_key)}, {sql_str_text(hit.chunk_key)}, 'brief', "
                f"{sql_str_text(query)}, {hit.final_score:.6f}, {sql_str_text('简报引用')})",
                note="记录简报来源",
            )
        return result, brief

    def stats(self) -> dict[str, Any]:
        """统计表行数、索引与记忆状态。"""
        counts = table_counts(self.db, self.settings.db_name)
        indexes: dict[str, list[dict[str, Any]]] = {}
        for table in ("papers", "paper_chunks"):
            indexes[table] = [
                {
                    "name": row.get("Key_name"),
                    "type": row.get("Index_type"),
                    "column": row.get("Column_name"),
                }
                for row in self.db.indexes_of(table)
            ]
        snapshot = self.load_memory()
        return {
            "server_version": self.db.server_version(),
            "db": f"{self.settings.db_host}:{self.settings.db_port}/{self.settings.db_name}",
            "tables": counts,
            "indexes": indexes,
            "memory": {
                "scope_id": snapshot.scope_id,
                "direction": snapshot.profile.direction,
                "tags": snapshot.profile.tags,
                "history": len(snapshot.history),
                "progress": len(snapshot.progress),
            },
        }


def sql_str_text(value: str) -> str:
    """把字符串转成 SQL 字面量（转义 :func:`paperpocket.sqlutil.sql_str`）。"""
    from .sqlutil import sql_str

    return sql_str(value)


def profile_to_dict(profile: MemoryProfile) -> dict[str, Any]:
    """把方向画像转成字典。"""
    return {"direction": profile.direction, "tags": profile.tags, "updated_at": profile.updated_at}
