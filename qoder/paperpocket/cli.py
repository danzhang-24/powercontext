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
"""命令行入口。

用法::

    python -m paperpocket <子命令> [参数]

子命令：

- ``ingest``——把语料目录里的论文 / 笔记导入 seekdb；
- ``search``——混合检索（BM25 全文 + 向量 ANN + 结构化过滤 + 记忆加权）；
- ``brief``——检索后生成研究简报（seekdb ``AI_COMPLETE``，无端点时本地降级）；
- ``recall``——读回 PowerContext 里保存的研究记忆；
- ``remember``——手动写入研究方向 / 标签；
- ``demo``——一条命令跑完整流程并产出技术使用记录；
- ``stats``——查看表行数、索引与记忆状态；
- ``reset``——清空数据库与记忆绑定。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .config import Settings, load_settings
from .demo import run_demo
from .memory import MemorySnapshot
from .records import write_db_query_record, write_memory_record, write_text
from .retrieval import SearchFilters, format_hits
from .schema import drop_all
from .service import PaperPocket


def _build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。"""
    parser = argparse.ArgumentParser(
        prog="python -m paperpocket",
        description="PaperPocket：基于 seekdb 混合检索 + PowerContext 记忆的研究资料助手",
    )
    parser.add_argument("--db-host", default=None, help="seekdb 地址（默认 127.0.0.1）")
    parser.add_argument("--db-port", type=int, default=None, help="seekdb 端口（默认 5881）")
    parser.add_argument("--db-name", default=None, help="数据库名（默认 paperpocket）")
    parser.add_argument("--powercontext-url", default=None, help="PowerContext Server 地址")
    parser.add_argument("--scope-id", default=None, help="PowerContext 作用域逻辑名")
    parser.add_argument("--corpus-dir", default=None, help="语料目录")
    parser.add_argument("--records-dir", default=None, help="技术使用记录输出目录")
    parser.add_argument(
        "--embed-mode",
        choices=("auto", "ai", "local"),
        default=None,
        help="向量化通道：auto=有 AI 模型就用 AI_EMBED，local=本地哈希嵌入",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")

    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="导入语料到 seekdb")
    ingest.add_argument("--corpus-dir", default=None, help="语料目录（覆盖全局参数）")
    ingest.add_argument("--max-chars", type=int, default=480, help="单个段落块的最大字符数")

    search = sub.add_parser("search", help="混合检索")
    search.add_argument("query", help="检索词")
    search.add_argument("--top-k", type=int, default=8, help="返回条数")
    search.add_argument("--year-from", type=int, default=None, help="起始年份（含）")
    search.add_argument("--year-to", type=int, default=None, help="结束年份（含）")
    search.add_argument("--tag", action="append", default=[], help="按标签过滤（可重复）")
    search.add_argument("--kind", action="append", default=[], help="按资料类型过滤（可重复）")
    search.add_argument("--no-memory", action="store_true", help="不读取 PowerContext 记忆")
    search.add_argument("--no-remember", action="store_true", help="不把本次检索写回记忆")
    search.add_argument("--exclude-read", action="store_true", help="排除记忆中已读过的资料")
    search.add_argument("--show-sql", action="store_true", help="打印本次执行的 SQL")

    brief = sub.add_parser("brief", help="生成研究简报")
    brief.add_argument("query", help="检索词")
    brief.add_argument("--top-k", type=int, default=6, help="参与摘要的段落数")
    brief.add_argument("--no-ai", action="store_true", help="强制使用本地抽取式摘要")
    brief.add_argument("--year-from", type=int, default=None, help="起始年份（含）")
    brief.add_argument("--year-to", type=int, default=None, help="结束年份（含）")
    brief.add_argument("--tag", action="append", default=[], help="按标签过滤（可重复）")

    sub.add_parser("recall", help="读回 PowerContext 记忆")

    remember = sub.add_parser("remember", help="写入研究方向与标签")
    remember.add_argument("--direction", required=True, help="研究方向描述")
    remember.add_argument("--tag", action="append", default=[], help="常用标签（可重复）")

    sub.add_parser("stats", help="查看表行数、索引与记忆状态")

    setup_ai = sub.add_parser("setup-ai", help="把本地模型服务注册到 seekdb（AI_EMBED / AI_COMPLETE）")
    setup_ai.add_argument(
        "--model-server-url",
        default=None,
        help="OpenAI 兼容模型服务地址（默认 http://127.0.0.1:8300/v1）",
    )

    verify_parser = sub.add_parser("verify", help="逐项自检验收要点")
    verify_parser.add_argument("--query", default="图神经网络 消息传递", help="自检使用的检索词")

    demo = sub.add_parser("demo", help="跑完整演示流程并产出技术使用记录")
    demo.add_argument("--query", default=None, help="演示检索词")
    demo.add_argument("--skip-ingest", action="store_true", help="跳过导入步骤")

    reset = sub.add_parser("reset", help="清空数据库与记忆绑定")
    reset.add_argument("--wipe-memory", action="store_true", help="同时丢弃本地作用域绑定")

    return parser


def _settings(args: argparse.Namespace) -> Settings:
    """按命令行参数装配配置。"""
    return load_settings(
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        powercontext_url=args.powercontext_url,
        scope_id=args.scope_id,
        corpus_dir=args.corpus_dir,
        records_dir=args.records_dir,
        embed_mode=args.embed_mode,
        model_server_url=getattr(args, "model_server_url", None),
    )


def _filters(args: argparse.Namespace) -> SearchFilters:
    """把命令行过滤参数转成 :class:`SearchFilters`。"""
    return SearchFilters(
        year_from=getattr(args, "year_from", None),
        year_to=getattr(args, "year_to", None),
        tags=list(getattr(args, "tag", []) or []),
        kinds=list(getattr(args, "kind", []) or []),
    )


def _print_snapshot(snapshot: MemorySnapshot) -> str:
    """把记忆快照渲染成文本。"""
    lines = [f"作用域：{snapshot.scope_id}"]
    lines.append(f"研究方向：{snapshot.profile.direction or '（空）'}")
    lines.append(f"常用标签：{','.join(snapshot.profile.tags) or '（空）'}")
    lines.append(f"历史检索次数：{len(snapshot.history)}")
    for item in snapshot.history[-5:]:
        lines.append(f"  - {item.at}　{item.query}　命中 {len(item.top_keys)} 段")
    lines.append(f"阅读进度条目：{len(snapshot.progress)}")
    for item in snapshot.progress[-5:]:
        lines.append(f"  - {item.at}　{item.status}　{item.title}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """命令行主函数，返回进程退出码。"""
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = _settings(args)
    app = PaperPocket(settings)

    try:
        if args.command == "ingest":
            corpus_dir = Path(args.corpus_dir) if args.corpus_dir else settings.corpus_dir
            with app:
                app.prepare_schema()
                report = app.ingest(corpus_dir, max_chars=args.max_chars)
            payload: dict[str, Any] = report.to_dict()
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(
                    f"已导入 {report.documents} 篇资料、{report.chunks} 个段落，"
                    f"清理旧数据 {report.deleted} 行，向量化通道：{report.embed_mode}"
                )
                for item in report.details:
                    print(f"  - {item['doc_key']}（{item['year']}）{item['title']}：{item['chunks']} 段")
            return 0

        if args.command == "search":
            with app:
                filters = _filters(args)
                if args.exclude_read:
                    snapshot = app.load_memory()
                    filters.exclude_doc_keys |= snapshot.read_doc_keys
                result = app.search(
                    args.query,
                    filters=filters,
                    top_k=args.top_k,
                    use_memory=not args.no_memory,
                    remember=not args.no_remember,
                )
                payload = result.to_dict()
                write_db_query_record(settings.records_dir, app.db.log)
                if app.memory_writes or app.memory_reads:
                    write_memory_record(settings.records_dir, app.memory_writes, app.memory_reads)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(format_hits(result, show_sql=args.show_sql))
            return 0

        if args.command == "brief":
            with app:
                result, brief = app.make_brief(
                    args.query,
                    filters=_filters(args),
                    top_k=args.top_k,
                    use_ai=not args.no_ai,
                )
                write_db_query_record(settings.records_dir, app.db.log)
                if app.memory_writes or app.memory_reads:
                    write_memory_record(settings.records_dir, app.memory_writes, app.memory_reads)
            if args.json:
                print(
                    json.dumps(
                        {"search": result.to_dict(), "brief": brief.to_dict()},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(f"简报（引擎：{brief.engine}，模型：{brief.model or '本地'}）：")
                print(brief.text)
                if brief.error:
                    print(f"（说明：{brief.error}）")
                print()
                print("引用段落：")
                for index, hit in enumerate(result.hits, start=1):
                    print(f"  [{index}] {hit.title} — {hit.source_path}:{hit.start_line}-{hit.end_line}")
            return 0

        if args.command == "recall":
            with app:
                snapshot = app.load_memory()
                write_memory_record(settings.records_dir, app.memory_writes, app.memory_reads)
            if args.json:
                print(
                    json.dumps(
                        {
                            "scope_id": snapshot.scope_id,
                            "profile": {
                                "direction": snapshot.profile.direction,
                                "tags": snapshot.profile.tags,
                            },
                            "history": [
                                {"query": item.query, "top_keys": item.top_keys, "at": item.at}
                                for item in snapshot.history
                            ],
                            "progress": [
                                {
                                    "doc_key": item.doc_key,
                                    "title": item.title,
                                    "status": item.status,
                                    "at": item.at,
                                }
                                for item in snapshot.progress
                            ],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(_print_snapshot(snapshot))
            return 0

        if args.command == "remember":
            with app:
                response = app.remember_profile(args.direction, list(args.tag or []))
                write_memory_record(settings.records_dir, app.memory_writes, app.memory_reads)
            if args.json:
                print(json.dumps(response, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"已写入记忆（作用域 {app.memory.ensure_scope()}）：")
                print(response.get("text", ""))
            return 0

        if args.command == "stats":
            with app:
                stats = app.stats()
                write_db_query_record(settings.records_dir, app.db.log)
            if args.json:
                print(json.dumps(stats, ensure_ascii=False, indent=2))
            else:
                print(f"seekdb 版本：{stats['server_version']}")
                print(f"数据库：{stats['db']}")
                for table, count in stats["tables"].items():
                    print(f"  表 {table}：{count} 行")
                for table, indexes in stats["indexes"].items():
                    names = ", ".join(
                        f"{item['name']}({item['type']}:{item['column']})" for item in indexes
                    )
                    print(f"  索引 {table}：{names}")
                memory = stats["memory"]
                print(
                    f"  记忆作用域：{memory['scope_id']}　方向：{memory['direction'] or '（空）'}"
                    f"　历史 {memory['history']} 条　进度 {memory['progress']} 条"
                )
            return 0

        if args.command == "setup-ai":
            with app:
                result = app.setup_ai_models()
                write_db_query_record(settings.records_dir, app.db.log)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"嵌入模型端点：{result['embedding_url']}（注册成功：{bool(result['embedding_model'])}）")
                print(f"摘要模型端点：{result['completion_url']}（注册成功：{bool(result['completion_model'])}）")
                for message in result["errors"]:
                    if "not found" not in message.lower():
                        print(f"  提示：{message}")
            return 0

        if args.command == "verify":
            from .verify import render, run_checks

            results = run_checks(app, query=args.query)
            text = render(results)
            if args.json:
                print(
                    json.dumps(
                        {
                            "passed": sum(1 for item in results if item.passed),
                            "total": len(results),
                            "checks": [
                                {"name": item.name, "passed": item.passed, "detail": item.detail}
                                for item in results
                            ],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(text)
            return 0 if all(item.passed for item in results) else 1

        if args.command == "demo":
            return run_demo(app, args)

        if args.command == "reset":
            with app:
                drop_all(app.db, settings.db_name)
                if args.wipe_memory:
                    app.memory.forget_scope()
            print("已清空数据库" + ("与记忆绑定" if args.wipe_memory else ""))
            return 0

    except Exception as exc:  # noqa: BLE001 - CLI 顶层需要友好报错
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1

    parser.error(f"未知子命令：{args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover - 脚本入口
    raise SystemExit(main())
