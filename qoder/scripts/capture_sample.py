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
#!/usr/bin/env python3
"""抓取一次真实检索的样本（检索词 + 命中行 + 通道耗时），落到 records/。

用法（在 qoder/ 目录下）::

    .venv/bin/python scripts/capture_sample.py --query "图神经网络 消息传递 邻居聚合"

产出：

- ``records/retrieval_sample.json``——机器可读：检索词、命中行、每条 SQL 的耗时；
- ``records/retrieval_sample.md``——人可读：排名表 + 通道说明。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

QODER_DIR = Path(__file__).resolve().parent.parent
if str(QODER_DIR) not in sys.path:
    sys.path.insert(0, str(QODER_DIR))

from paperpocket.config import load_settings  # noqa: E402
from paperpocket.service import PaperPocket  # noqa: E402


def _hit_row(index: int, hit) -> str:
    """把一条命中渲染成 Markdown 表格行。"""
    bm25 = "-" if hit.bm25_score is None else "%.6f" % hit.bm25_score
    ann = "-" if hit.ann_distance is None else "%.6f" % hit.ann_distance
    lanes = "+".join(hit.lanes)
    source = "%s:%d-%d" % (hit.source_path, hit.start_line, hit.end_line)
    return "| %d | %s | %d | `%s` | %.6f | %.6f | %s | %s | %s |" % (
        index, hit.title, hit.year, source, hit.final_score, hit.rrf_score, bm25, ann, lanes,
    )


def main() -> int:
    """执行一次检索并写出样本文件。"""
    parser = argparse.ArgumentParser(description="抓取一次真实检索的样本")
    parser.add_argument("--query", default="图神经网络 消息传递 邻居聚合", help="检索词")
    parser.add_argument("--top-k", type=int, default=5, help="返回条数")
    parser.add_argument("--no-memory", action="store_true", help="不读取 PowerContext 记忆")
    parser.add_argument("--records-dir", default=None, help="记录输出目录")
    args = parser.parse_args()

    settings = load_settings(records_dir=args.records_dir)
    app = PaperPocket(settings)
    with app:
        started = time.perf_counter()
        result = app.search(
            args.query,
            top_k=args.top_k,
            use_memory=not args.no_memory,
            remember=False,
        )
        total_ms = (time.perf_counter() - started) * 1000
        lane_timing = {}
        for record in app.db.log:
            if "通道" in record.step:
                lane_timing[record.step] = {
                    "sql": record.sql,
                    "row_count": record.row_count,
                    "elapsed_ms": round(record.elapsed_ms, 3),
                }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db": "%s:%s/%s" % (settings.db_host, settings.db_port, settings.db_name),
        "query": result.query,
        "top_k": args.top_k,
        "candidate_count": result.candidate_count,
        "total_elapsed_ms": round(total_ms, 3),
        "lane_timing": lane_timing,
        "memory_applied": result.memory_applied,
        "hits": [hit.to_dict() for hit in result.hits],
        "sql": {"bm25": result.bm25_sql, "vector": result.ann_sql},
    }

    records_dir = settings.records_dir
    records_dir.mkdir(parents=True, exist_ok=True)
    json_path = records_dir / "retrieval_sample.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 检索样本（真实运行抓取）",
        "",
        "- 抓取时间：%s" % payload["generated_at"],
        "- 数据库：`%s`" % payload["db"],
        "- 检索词：`%s`" % payload["query"],
        "- 候选段落数：%d，返回条数：%d" % (result.candidate_count, len(result.hits)),
        "- 端到端耗时：%.3f ms" % payload["total_elapsed_ms"],
        "",
        "## 各通道耗时",
        "",
        "| 通道 | 命中行数 | 耗时(ms) |",
        "| --- | --- | --- |",
    ]
    for step, item in lane_timing.items():
        lines.append("| %s | %d | %.3f |" % (step, item["row_count"], item["elapsed_ms"]))
    lines.extend([
        "",
        "## 命中结果",
        "",
        "| # | 标题 | 年份 | 来源 | 最终分 | RRF | BM25 | ANN 距离 | 通道 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for index, hit in enumerate(result.hits, start=1):
        lines.append(_hit_row(index, hit))
    md_path = records_dir / "retrieval_sample.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("检索词：%s" % result.query)
    print("命中 %d 条（候选 %d），耗时 %.3f ms" % (
        len(result.hits), result.candidate_count, payload["total_elapsed_ms"]))
    for step, item in lane_timing.items():
        print("  %s：%d 行，%.3f ms" % (step, item["row_count"], item["elapsed_ms"]))
    print("已写出 %s" % json_path)
    print("已写出 %s" % md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
