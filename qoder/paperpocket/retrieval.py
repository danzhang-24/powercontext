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
"""混合检索：BM25 全文 + 向量 ANN + 结构化过滤 + 融合排序。

检索分三条通道并行：

1. **全文通道（BM25）**——``MATCH(title, content) AGAINST('...' IN NATURAL LANGUAGE MODE)``
   走 seekdb 的 ngram 全文索引，返回相关度分数。
2. **向量通道（ANN）**——``l2_distance(emb, '[...]')`` 配合 HNSW 向量索引，
   ``ORDER BY ... APPROXIMATE LIMIT n`` 取近似最近邻。
3. **记忆通道（PowerContext）**——把上次记住的研究方向、常用标签与历史检索
   折算成加分项，同时用记忆里的方向扩展查询向量。

三条通道的结果用 RRF（Reciprocal Rank Fusion）融合，再叠加记忆加权，得到
最终排序。结构化条件（年份区间、标签、资料类型、已读资料）直接写在两条
SQL 的 ``WHERE`` 里，由数据库完成过滤。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .db import SeekDB
from .embedding import Embedder, blend, tokenize
from .memory import MemorySnapshot
from .sqlutil import sql_int, sql_like, sql_str, sql_vector

#: RRF 平滑常数。
RRF_K = 60

#: 记忆加权的最大系数。
MEMORY_WEIGHT = 0.35

#: 命中片段的上下文长度（字符）。
SNIPPET_RADIUS = 160


@dataclass
class SearchFilters:
    """结构化过滤条件。"""

    year_from: int | None = None
    year_to: int | None = None
    tags: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    exclude_doc_keys: set[str] = field(default_factory=set)

    def where_clause(self) -> str:
        """生成 SQL ``WHERE`` 片段（不含 ``WHERE`` 关键字）。"""
        parts: list[str] = []
        if self.year_from is not None:
            parts.append(f"year >= {sql_int(self.year_from)}")
        if self.year_to is not None:
            parts.append(f"year <= {sql_int(self.year_to)}")
        for tag in self.tags:
            parts.append(f"tags LIKE {sql_str(sql_like(tag))}")
        for kind in self.kinds:
            parts.append(f"kind = {sql_str(kind)}")
        return " AND ".join(parts)


@dataclass
class SearchHit:
    """一条检索命中。"""

    chunk_key: str
    doc_key: str
    title: str
    authors: str
    year: int
    venue: str
    tags: list[str]
    heading: str
    seq: int
    source_path: str
    start_line: int
    end_line: int
    content: str
    bm25_rank: int | None = None
    bm25_score: float | None = None
    ann_rank: int | None = None
    ann_distance: float | None = None
    memory_score: float = 0.0
    memory_reason: list[str] = field(default_factory=list)
    rrf_score: float = 0.0
    final_score: float = 0.0
    snippet: str = ""

    @property
    def lanes(self) -> list[str]:
        """该命中参与的通道。"""
        lanes: list[str] = []
        if self.bm25_rank is not None:
            lanes.append("bm25")
        if self.ann_rank is not None:
            lanes.append("vector")
        if self.memory_score > 0:
            lanes.append("memory")
        return lanes

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "chunk_key": self.chunk_key,
            "doc_key": self.doc_key,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "tags": self.tags,
            "heading": self.heading,
            "source_path": self.source_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "snippet": self.snippet,
            "bm25_rank": self.bm25_rank,
            "bm25_score": self.bm25_score,
            "ann_rank": self.ann_rank,
            "ann_distance": self.ann_distance,
            "memory_score": round(self.memory_score, 4),
            "memory_reason": self.memory_reason,
            "rrf_score": round(self.rrf_score, 6),
            "final_score": round(self.final_score, 6),
            "lanes": self.lanes,
        }


@dataclass
class SearchResult:
    """一次检索的完整结果。"""

    query: str
    hits: list[SearchHit]
    bm25_sql: str = ""
    ann_sql: str = ""
    memory_applied: dict[str, Any] = field(default_factory=dict)
    candidate_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "query": self.query,
            "hits": [hit.to_dict() for hit in self.hits],
            "sql": {"bm25": self.bm25_sql, "vector": self.ann_sql},
            "memory_applied": self.memory_applied,
            "candidate_count": self.candidate_count,
        }


def _row_to_hit(row: dict[str, Any]) -> SearchHit:
    """把一行查询结果转成 :class:`SearchHit`。"""
    tags_text = str(row.get("tags") or "")
    return SearchHit(
        chunk_key=str(row.get("chunk_key") or ""),
        doc_key=str(row.get("doc_key") or ""),
        title=str(row.get("title") or ""),
        authors=str(row.get("authors") or ""),
        year=int(row.get("year") or 0),
        venue=str(row.get("venue") or ""),
        tags=[tag.strip() for tag in tags_text.split(",") if tag.strip()],
        heading=str(row.get("heading") or ""),
        seq=int(row.get("seq") or 0),
        source_path=str(row.get("source_path") or ""),
        start_line=int(row.get("start_line") or 0),
        end_line=int(row.get("end_line") or 0),
        content=str(row.get("content") or ""),
    )


def make_snippet(content: str, query: str, radius: int = SNIPPET_RADIUS) -> str:
    """截取命中位置附近的片段。"""
    text = content.replace("\r", "")
    if not text:
        return ""
    lowered = text.lower()
    best_pos = -1
    best_hits = 0
    for token in tokenize(query):
        if len(token) < 2:
            continue
        position = lowered.find(token)
        if position < 0:
            continue
        count = lowered.count(token)
        if count > best_hits:
            best_hits = count
            best_pos = position
    if best_pos < 0:
        return text[: radius * 2].strip()
    start = max(0, best_pos - radius)
    end = min(len(text), best_pos + radius)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


class HybridSearch:
    """混合检索器。"""

    def __init__(self, db: SeekDB, embedder: Embedder, db_name: str) -> None:
        self.db = db
        self.embedder = embedder
        self.db_name = db_name

    # -- SQL --------------------------------------------------------------
    def _bm25_sql(self, query: str, filters: SearchFilters, limit: int) -> str:
        """生成 BM25 全文检索语句。"""
        match = f"MATCH(title, content) AGAINST ({sql_str(query)} IN NATURAL LANGUAGE MODE)"
        where = filters.where_clause()
        clause = f"WHERE {match}"
        if where:
            clause += f" AND {where}"
        return (
            "SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, "
            "source_path, start_line, end_line, content, "
            f"{match} AS bm25_score FROM {self.db_name}.paper_chunks {clause} "
            f"ORDER BY bm25_score DESC LIMIT {sql_int(limit)}"
        )

    def _ann_sql(self, vector: list[float], filters: SearchFilters, limit: int) -> str:
        """生成向量 ANN 检索语句。"""
        literal = sql_vector(vector)
        where = filters.where_clause()
        clause = f"WHERE {where}" if where else ""
        return (
            "SELECT chunk_key, doc_key, title, authors, year, venue, tags, heading, seq, "
            "source_path, start_line, end_line, content, "
            f"l2_distance(emb, {literal}) AS ann_distance FROM {self.db_name}.paper_chunks {clause} "
            f"ORDER BY l2_distance(emb, {literal}) APPROXIMATE LIMIT {sql_int(limit)}"
        )

    # -- 记忆 -------------------------------------------------------------
    def _memory_scores(
        self, hits: dict[str, SearchHit], snapshot: MemorySnapshot | None
    ) -> dict[str, Any]:
        """计算记忆通道得分，并返回可解释的记忆应用说明。"""
        applied: dict[str, Any] = {
            "enabled": snapshot is not None and not snapshot.is_empty,
            "scope_id": snapshot.scope_id if snapshot else "",
            "direction": snapshot.profile.direction if snapshot else "",
            "tags": snapshot.profile.tags if snapshot else [],
            "history_queries": [item.query for item in snapshot.history] if snapshot else [],
            "read_doc_keys": sorted(snapshot.read_doc_keys) if snapshot else [],
            "excluded_doc_keys": [],
            "boosted": [],
        }
        if snapshot is None or snapshot.is_empty:
            return applied

        direction_tokens = [token.lower() for token in snapshot.profile.keywords]
        history_keys = {key for item in snapshot.history for key in item.top_keys}
        memory_tags = {tag.lower() for tag in snapshot.profile.tags}

        for hit in hits.values():
            score = 0.0
            reasons: list[str] = []
            hit_tags = {tag.lower() for tag in hit.tags}
            matched_tags = hit_tags & memory_tags
            if matched_tags:
                score += 2.0 * min(len(matched_tags), 2) / 2.0
                reasons.append(f"命中记忆标签 {sorted(matched_tags)}")
            haystack = f"{hit.title}\n{hit.heading}\n{hit.content}".lower()
            direction_hits = [token for token in direction_tokens if token and token in haystack]
            if direction_hits:
                score += 0.5 * min(len(direction_hits), 4)
                reasons.append(f"命中记忆方向关键词 {direction_hits[:4]}")
            if hit.chunk_key in history_keys or hit.doc_key in history_keys:
                score += 1.0
                reasons.append("出现在历史检索命中中")
            hit.memory_score = score
            hit.memory_reason = reasons
            if reasons:
                applied["boosted"].append({"chunk_key": hit.chunk_key, "reason": reasons})

        return applied

    # -- 主流程 -----------------------------------------------------------
    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        top_k: int = 8,
        candidate_limit: int = 40,
        snapshot: MemorySnapshot | None = None,
        use_memory: bool = True,
    ) -> SearchResult:
        """执行一次混合检索。"""
        filters = filters or SearchFilters()
        memory = snapshot if use_memory else None

        # 1) 查询向量：有记忆时用研究方向扩展，向量通道因此也受记忆影响。
        query_vector = self.embedder.embed(query)
        if memory and memory.profile.direction:
            direction_vector = self.embedder.embed(memory.profile.direction)
            query_vector = blend([query_vector, direction_vector], [1.0, 0.35])

        # 2) 全文通道。
        bm25_sql = self._bm25_sql(query, filters, candidate_limit)
        self.db.step("混合检索-全文通道")
        bm25_rows = self.db.query(bm25_sql, note="BM25 全文检索")

        # 3) 向量通道。
        ann_sql = self._ann_sql(query_vector, filters, candidate_limit)
        self.db.step("混合检索-向量通道")
        ann_rows = self.db.query(ann_sql, note="向量 ANN 检索")

        hits: dict[str, SearchHit] = {}
        for rank, row in enumerate(bm25_rows, start=1):
            hit = _row_to_hit(row)
            hit.bm25_rank = rank
            hit.bm25_score = float(row.get("bm25_score") or 0.0)
            hits[hit.chunk_key] = hit
        for rank, row in enumerate(ann_rows, start=1):
            hit = _row_to_hit(row)
            hit.ann_rank = rank
            hit.ann_distance = float(row.get("ann_distance") or 0.0)
            existing = hits.get(hit.chunk_key)
            if existing is None:
                hits[hit.chunk_key] = hit
            else:
                existing.ann_rank = rank
                existing.ann_distance = hit.ann_distance

        # 4) 记忆通道 + 已读过滤。
        memory_applied = self._memory_scores(hits, memory)
        if memory and memory.read_doc_keys:
            dropped = [key for key, hit in hits.items() if hit.doc_key in memory.read_doc_keys]
            for key in dropped:
                hits.pop(key, None)
            memory_applied["excluded_doc_keys"] = sorted(memory.read_doc_keys)
            memory_applied["excluded_count"] = len(dropped)
        if filters.exclude_doc_keys:
            for key in [k for k, hit in hits.items() if hit.doc_key in filters.exclude_doc_keys]:
                hits.pop(key, None)

        # 5) RRF 融合。
        for hit in hits.values():
            rrf = 0.0
            if hit.bm25_rank is not None:
                rrf += 1.0 / (RRF_K + hit.bm25_rank)
            if hit.ann_rank is not None:
                rrf += 1.0 / (RRF_K + hit.ann_rank)
            hit.rrf_score = rrf
            boost = 1.0 + MEMORY_WEIGHT * hit.memory_score
            hit.final_score = rrf * boost
            hit.snippet = make_snippet(hit.content, query)

        ordered = sorted(hits.values(), key=lambda item: (-item.final_score, item.chunk_key))
        return SearchResult(
            query=query,
            hits=ordered[:top_k],
            bm25_sql=bm25_sql,
            ann_sql=ann_sql,
            memory_applied=memory_applied,
            candidate_count=len(ordered),
        )


def format_hits(result: SearchResult, show_sql: bool = True) -> str:
    """把检索结果渲染成可读文本。"""
    lines: list[str] = [f"检索词：{result.query}", f"候选段落数：{result.candidate_count}", ""]
    memory = result.memory_applied
    if memory.get("enabled"):
        lines.append(
            "已应用 PowerContext 记忆：方向={direction}，标签={tags}，历史检索={history}".format(
                direction=memory.get("direction") or "（空）",
                tags=",".join(memory.get("tags") or []) or "（空）",
                history=memory.get("history_queries") or [],
            )
        )
        if memory.get("excluded_doc_keys"):
            lines.append(f"已按阅读进度排除资料：{memory['excluded_doc_keys']}")
        lines.append("")
    if not result.hits:
        lines.append("（没有命中任何段落）")
    for index, hit in enumerate(result.hits, start=1):
        lines.append(f"[{index}] {hit.title}（{hit.year}）· {hit.heading}")
        lines.append(
            f"    来源：{hit.source_path}:{hit.start_line}-{hit.end_line}　标签：{','.join(hit.tags)}"
        )
        lines.append(
            f"    分数：{hit.final_score:.6f}（rrf={hit.rrf_score:.6f}，"
            f"通道={'+'.join(hit.lanes)}）"
        )
        if hit.bm25_score is not None:
            lines.append(f"    BM25={hit.bm25_score:.6f}　ANN距离={hit.ann_distance:.6f}")
        if hit.memory_reason:
            lines.append(f"    记忆加权：{hit.memory_score:.2f}（{'；'.join(hit.memory_reason)}）")
        lines.append(f"    片段：{hit.snippet}")
        lines.append("")
    if show_sql:
        lines.append("--- 全文通道 SQL ---")
        lines.append(result.bm25_sql)
        lines.append("--- 向量通道 SQL ---")
        lines.append(result.ann_sql)
    return "\n".join(lines)


def tags_from_text(text: str) -> list[str]:
    """从逗号分隔的文本里解析标签。"""
    return [part.strip() for part in re.split(r"[,，]", text) if part.strip()]


def merge_filters(*filters: Iterable[SearchFilters]) -> SearchFilters:
    """合并多个过滤条件。"""
    merged = SearchFilters()
    for item in filters:
        merged.year_from = item.year_from if merged.year_from is None else min(merged.year_from, item.year_from)
        merged.year_to = item.year_to if merged.year_to is None else max(merged.year_to, item.year_to)
        merged.tags.extend(item.tags)
        merged.kinds.extend(item.kinds)
        merged.exclude_doc_keys |= item.exclude_doc_keys
    return merged
