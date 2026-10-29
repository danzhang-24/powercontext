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
"""端到端演示编排。

``python -m paperpocket demo`` 会按下面的顺序跑一遍，并把每一步的真实输出
写进 ``records/``：

1. 建库建表、创建全文索引与向量索引；
2. 导入演示语料（论文 + 课程笔记 + 实验记录）；
3. **第一次检索**——此时 PowerContext 里还没有记忆；
4. 把研究方向、常用标签写进 PowerContext（同时检索历史自动写入）；
5. **第二次检索**——读回上一步的记忆，方向参与向量查询扩展、标签参与加权；
6. 生成研究简报（seekdb ``AI_COMPLETE``）；
7. 记录阅读进度（写回 PowerContext）；
8. ``recall`` 读回全部记忆，验证"第二次读到了第一次写下的内容"。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .records import write_db_query_record, write_memory_record, write_text
from .retrieval import SearchFilters, format_hits
from .service import PaperPocket

#: 演示默认检索词。
DEFAULT_QUERY = "图神经网络 消息传递 邻居聚合"

#: 演示写入记忆的研究方向。
DEFAULT_DIRECTION = "图神经网络 消息传递"

#: 演示写入记忆的常用标签。
DEFAULT_TAGS = ["gnn", "message-passing"]


def _top_keys(result: Any, count: int = 5) -> list[str]:
    """取出命中结果的段落键。"""
    return [hit.chunk_key for hit in result.hits[:count]]


def run_demo(app: PaperPocket, args: argparse.Namespace) -> int:
    """执行演示流程，返回退出码。"""
    settings = app.settings
    query: str = args.query or DEFAULT_QUERY
    direction: str = DEFAULT_DIRECTION
    tags: list[str] = list(DEFAULT_TAGS)
    records_dir = settings.records_dir
    transcript: list[str] = []

    def say(text: str) -> None:
        """把演示输出同时写到终端与记录。"""
        print(text)
        transcript.append(text)

    with app:
        say("=" * 72)
        say("PaperPocket 端到端演示")
        say("=" * 72)
        say(f"seekdb：{settings.db_host}:{settings.db_port}/{settings.db_name}")
        say(f"PowerContext：{settings.powercontext_url}")
        say(f"语料目录：{settings.corpus_dir}")
        say("")

        say("【步骤 1】准备表结构、全文索引与向量索引")
        app.prepare_schema()
        say(f"  建表完成；向量维度 {settings.embed_dim}")

        if not args.skip_ingest:
            say("")
            say("【步骤 2】导入论文与笔记")
            report = app.ingest()
            say(f"  导入 {report.documents} 篇资料、{report.chunks} 个段落，"
                f"清理旧数据 {report.deleted} 行")
            say(f"  向量化通道：{report.embed_mode}"
                f"（{'seekdb AI_EMBED' if report.embed_mode == 'ai' else '本地确定性哈希嵌入'}）")
            for item in report.details:
                say(f"    - {item['doc_key']}（{item['year']}）{item['title']}：{item['chunks']} 段")

        say("")
        say("【步骤 3】第一次检索（此时 PowerContext 中还没有记忆）")
        first = app.search(query, filters=SearchFilters(), top_k=5, use_memory=True, remember=True)
        say(format_hits(first, show_sql=False))
        say("  本次执行的 SQL：")
        for record in app.db.log[-2:]:
            say(f"    {record.sql}")

        say("")
        say("【步骤 4】把研究方向与常用标签写入 PowerContext")
        app.remember_profile(direction, tags)
        say(f"  已写入：direction={direction}，tags={tags}")
        say(f"  作用域：{app.memory.ensure_scope()}")

        say("")
        say("【步骤 5】第二次检索（读回上一步写入的记忆）")
        snapshot = app.load_memory()
        say(f"  读回记忆：方向={snapshot.profile.direction or '（空）'}"
            f"，标签={snapshot.profile.tags}，历史检索={len(snapshot.history)} 条")
        second = app.search(query, filters=SearchFilters(), top_k=5, use_memory=True, remember=True)
        say(format_hits(second, show_sql=False))
        say("  与第一次检索的差异：")
        first_keys = [hit.chunk_key for hit in first.hits]
        second_keys = [hit.chunk_key for hit in second.hits]
        say(f"    第一次：{first_keys}")
        say(f"    第二次：{second_keys}")
        say(f"    排序变化：{'是' if first_keys != second_keys else '否'}")

        say("")
        say("【步骤 6】生成研究简报（seekdb AI_COMPLETE）")
        brief_result, brief = app.make_brief(query, filters=SearchFilters(), top_k=5)
        say(f"  简报引擎：{brief.engine}，模型：{brief.model or '（本地抽取式）'}")
        if brief.error:
            say(f"  说明：{brief.error}")
        say(brief.text)
        say("  引用的段落：")
        for index, hit in enumerate(brief_result.hits, start=1):
            say(f"    [{index}] {hit.title} — {hit.source_path}:{hit.start_line}-{hit.end_line}")

        say("")
        say("【步骤 7】记录阅读进度（写回 PowerContext）")
        if brief_result.hits:
            first_hit = brief_result.hits[0]
            app.remember_progress(first_hit.doc_key, first_hit.title, status="read")
            say(f"  已记录：{first_hit.title}（{first_hit.doc_key}）")

        say("")
        say("【步骤 8】读回全部记忆，验证“第二次读到了第一次写下的内容”")
        final_snapshot = app.load_memory()
        say(f"  作用域：{final_snapshot.scope_id}")
        say(f"  方向：{final_snapshot.profile.direction or '（空）'}")
        say(f"  标签：{final_snapshot.profile.tags}")
        say(f"  历史检索：{[item.query for item in final_snapshot.history]}")
        say(f"  阅读进度：{[(item.title, item.status) for item in final_snapshot.progress]}")
        say(f"  记忆条目总数：{len(final_snapshot.raw_entries)}")

        db_md, db_json = write_db_query_record(records_dir, app.db.log)
        mem_md, mem_json = write_memory_record(
            records_dir, app.memory_writes, app.memory_reads
        )

    say("")
    say("=" * 72)
    say("产出记录：")
    say(f"  {db_md}")
    say(f"  {db_json}")
    say(f"  {mem_md}")
    say(f"  {mem_json}")
    say("=" * 72)

    write_text(records_dir / "demo_output.md", "\n".join(transcript) + "\n")
    write_text(records_dir / "demo_run.log", "\n".join(transcript) + "\n")
    return 0


def demo_records_dir(app: PaperPocket) -> Path:
    """返回记录目录（供脚本调用）。"""
    return app.settings.records_dir
