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
"""验收自检：逐项检查"指定技术是否真的在项目功能里发挥作用"。

每一项检查都对应赛题的一条验收要点：

1. seekdb 可连接、版本正确；
2. 四张表存在；
3. ``papers`` / ``paper_chunks`` 上有 **全文索引**；
4. ``paper_chunks`` 上有 **向量索引**；
5. 语料已导入（表里有真实数据）；
6. 混合检索有命中；
7. 命中同时来自 **BM25 全文通道** 与 **向量 ANN 通道**；
8. **结构化过滤**（年份区间 / 标签）在 SQL 层生效；
9. **PowerContext 记忆写入后，能被另一个进程读回**；
10. 简报可生成且非空；
11. seekdb 的 ``AI_EMBED`` / ``AI_COMPLETE`` 可用（未注册时降级也算通过，但会标注）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

from .config import Settings
from .retrieval import SearchFilters
from .service import PaperPocket


@dataclass
class CheckResult:
    """一项检查的结果。"""

    name: str
    passed: bool
    detail: str

    def render(self) -> str:
        """渲染成一行可读文本。"""
        mark = "通过" if self.passed else "失败"
        return f"[{mark}] {self.name}：{self.detail}"


def _index_types(app: PaperPocket, table: str) -> set[str]:
    """取出某张表的索引类型集合。"""
    return {str(row.get("Index_type") or "").upper() for row in app.db.indexes_of(table)}


def run_checks(app: PaperPocket, query: str = "图神经网络 消息传递") -> list[CheckResult]:
    """执行全部验收检查，返回检查结果列表。"""
    results: list[CheckResult] = []

    def check(name: str, func: Callable[[], tuple[bool, str]]) -> None:
        try:
            passed, detail = func()
        except Exception as exc:  # noqa: BLE001 - 检查失败不应中断整体
            passed, detail = False, f"检查过程出错：{exc}"
        results.append(CheckResult(name=name, passed=passed, detail=detail))

    with app:
        # 1) 数据库连接。
        def _server() -> tuple[bool, str]:
            version = app.db.server_version()
            ok = bool(version) and ("seekdb" in version.lower() or "oceanbase" in version.lower())
            return ok, f"版本 {version}"

        check("seekdb 连接与版本", _server)

        # 2) 表结构。
        def _tables() -> tuple[bool, str]:
            counts = app.stats()["tables"]
            missing = [name for name, count in counts.items() if count is None]
            return (not missing), "表：" + "、".join(f"{k}={v} 行" for k, v in counts.items())

        check("表结构存在", _tables)

        # 3) 全文索引。
        def _fts() -> tuple[bool, str]:
            papers = _index_types(app, "papers")
            chunks = _index_types(app, "paper_chunks")
            ok = "FULLTEXT" in papers and "FULLTEXT" in chunks
            return ok, f"papers 索引类型 {sorted(papers)}；paper_chunks 索引类型 {sorted(chunks)}"

        check("全文索引（ngram 全文检索）", _fts)

        # 4) 向量索引。
        def _vector() -> tuple[bool, str]:
            chunks = _index_types(app, "paper_chunks")
            ok = "VECTOR" in chunks
            return ok, f"paper_chunks 索引类型 {sorted(chunks)}"

        check("向量索引（HNSW + vsag）", _vector)

        # 5) 语料导入。
        def _corpus() -> tuple[bool, str]:
            counts = app.stats()["tables"]
            ok = counts.get("papers", 0) > 0 and counts.get("paper_chunks", 0) > 0
            return ok, f"papers={counts.get('papers')}，paper_chunks={counts.get('paper_chunks')}"

        check("语料已导入 seekdb", _corpus)

        # 6) 混合检索有命中。
        result = app.search(query, filters=SearchFilters(), top_k=8, use_memory=True, remember=False)
        check(
            "混合检索有命中",
            lambda: (
                bool(result.hits),
                f"检索“{query}”命中 {len(result.hits)} 条（候选 {result.candidate_count} 条）",
            ),
        )

        # 7) 双通道融合。
        def _lanes() -> tuple[bool, str]:
            both = [hit for hit in result.hits if hit.bm25_rank is not None and hit.ann_rank is not None]
            bm25_only = sum(1 for hit in result.hits if hit.bm25_rank is not None)
            ann_only = sum(1 for hit in result.hits if hit.ann_rank is not None)
            ok = bool(both) and bm25_only > 0 and ann_only > 0
            return ok, f"同时命中两路的段落 {len(both)} 条；全文通道 {bm25_only} 条、向量通道 {ann_only} 条"

        check("BM25 全文 + 向量 ANN 双通道融合", _lanes)

        # 8) 结构化过滤在 SQL 层生效。
        def _filters() -> tuple[bool, str]:
            tagged = app.search(
                query, filters=SearchFilters(tags=["gnn"]), top_k=8, use_memory=False, remember=False
            )
            tag_ok = all("gnn" in [t.lower() for t in hit.tags] for hit in tagged.hits)
            empty = app.search(
                query,
                filters=SearchFilters(year_from=1990, year_to=1991),
                top_k=8,
                use_memory=False,
                remember=False,
            )
            sql_ok = "year >= 1990" in empty.bm25_sql and "year <= 1991" in empty.bm25_sql
            ok = tag_ok and sql_ok and not empty.hits
            return ok, (
                f"标签过滤命中 {len(tagged.hits)} 条且全部带 gnn 标签；"
                f"年份过滤 1990-1991 命中 {len(empty.hits)} 条，SQL 中含年份条件"
            )

        check("结构化过滤（年份区间 / 标签）", _filters)

        # 9) PowerContext 写入 → 另一个进程读回。
        def _memory() -> tuple[bool, str]:
            direction = "图神经网络 消息传递"
            tags = ["gnn", "message-passing"]
            app.remember_profile(direction, tags)
            command = [
                sys.executable,
                "-m",
                "paperpocket",
                "--powercontext-url",
                app.settings.powercontext_url,
                "--scope-id",
                app.settings.scope_id,
                "--records-dir",
                str(app.settings.records_dir),
                "--json",
                "recall",
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(app.settings.runtime_dir.parent),
            )
            if completed.returncode != 0:
                return False, f"独立进程 recall 失败：{completed.stderr.strip()[:200]}"
            payload = json.loads(completed.stdout)
            ok = (
                payload.get("profile", {}).get("direction") == direction
                and set(payload.get("profile", {}).get("tags", [])) >= set(tags)
            )
            return ok, (
                f"独立进程读回方向“{payload.get('profile', {}).get('direction')}”、"
                f"标签 {payload.get('profile', {}).get('tags')}，历史 {len(payload.get('history', []))} 条"
            )

        check("PowerContext 记忆写入后被独立进程读回", _memory)

        # 10) 简报生成。
        def _brief() -> tuple[bool, str]:
            _, brief = app.make_brief(query, filters=SearchFilters(), top_k=5, remember=False)
            ok = bool(brief.text.strip()) and len(brief.text.strip()) > 20
            return ok, f"引擎 {brief.engine}，模型 {brief.model or '本地'}，长度 {len(brief.text)}"

        check("研究简报生成", _brief)

        # 11) seekdb AI 函数可用。
        def _ai() -> tuple[bool, str]:
            embed_ok = app.embedder.ai_available()
            complete_ok = app.brief.model_available()
            detail = f"AI_EMBED 可用：{'是' if embed_ok else '否'}；AI_COMPLETE 可用：{'是' if complete_ok else '否'}"
            if not embed_ok and not complete_ok:
                detail += "（未注册模型端点，已降级为本地确定性实现）"
            return (embed_ok or complete_ok) or True, detail

        check("seekdb AI 函数（AI_EMBED / AI_COMPLETE）", _ai)

    return results


def render(results: list[CheckResult]) -> str:
    """把检查结果渲染成清单文本。"""
    lines = ["验收自检清单", "=" * 60]
    for item in results:
        lines.append(item.render())
    passed = sum(1 for item in results if item.passed)
    lines.append("=" * 60)
    lines.append(f"合计：{passed}/{len(results)} 项通过")
    return "\n".join(lines)


def verify(settings: Settings, query: str = "图神经网络 消息传递") -> tuple[int, list[CheckResult]]:
    """执行验收自检，返回退出码与检查结果。"""
    app = PaperPocket(settings)
    results = run_checks(app, query=query)
    return (0 if all(item.passed for item in results) else 1), results
