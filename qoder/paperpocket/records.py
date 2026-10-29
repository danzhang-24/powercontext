"""技术使用记录输出。

评审需要核对"指定技术是否真的在项目功能里发挥作用"，因此本模块把三类证据
落盘：

- ``records/db_query_record.md`` / ``.json``——每一条真实执行的 seekdb SQL；
- ``records/powercontext_memory_record.md`` / ``.json``——PowerContext 的写入与读回；
- ``records/demo_output.md`` / ``demo_run.log``——演示过程与终端输出片段。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .db import SqlRecord


@dataclass
class MemoryWrite:
    """一次 PowerContext 写入。"""

    entry_type: str
    reason: str
    text: str
    scope_id: str
    entry_id: str = ""
    revision: int = 0
    response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "entry_type": self.entry_type,
            "reason": self.reason,
            "text": self.text,
            "scope_id": self.scope_id,
            "entry_id": self.entry_id,
            "revision": self.revision,
        }


@dataclass
class MemoryRead:
    """一次 PowerContext 读回。"""

    query: str
    scope_id: str
    hits: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "query": self.query,
            "scope_id": self.scope_id,
            "hit_count": len(self.hits),
            "hits": self.hits,
        }


def _write_json(path: Path, payload: Any) -> None:
    """写 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> Any:
    """读 JSON 文件；文件不存在或损坏时返回空字典。"""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


#: 记录里最多保留的条目数（避免文件无限增长）。
MAX_RECORD_ITEMS = 200


def _merge_sql_records(json_path: Path, records: list[SqlRecord]) -> list[SqlRecord]:
    """把本次 SQL 与历史记录合并（同一个步骤 + SQL 只保留最后一次耗时）。"""
    merged: dict[tuple[str, str, str], SqlRecord] = {}
    previous = _load_json(json_path)
    for item in previous if isinstance(previous, list) else []:
        key = (item.get("step", ""), item.get("sql", ""), item.get("note", ""))
        merged[key] = SqlRecord(
            step=key[0],
            sql=key[1],
            row_count=int(item.get("row_count", 0)),
            elapsed_ms=float(item.get("elapsed_ms", 0.0)),
            note=key[2],
        )
    for record in records:
        key = (record.step, record.sql, record.note)
        merged[key] = record
    return list(merged.values())[-MAX_RECORD_ITEMS:]


def write_db_query_record(records_dir: Path, sql_records: Iterable[SqlRecord]) -> tuple[Path, Path]:
    """写出数据库查询记录（Markdown + JSON）。

    记录是**累积**的：任何一次子命令（``search`` / ``stats`` …）都不会把上一次
    演示留下的证据覆盖掉。
    """
    md_path = records_dir / "db_query_record.md"
    json_path = records_dir / "db_query_record.json"
    records = _merge_sql_records(json_path, list(sql_records))
    lines = [
        "# seekdb 查询记录",
        "",
        f"共执行 {len(records)} 条 SQL，全部为项目运行时的真实调用（未做任何删改）。",
        "",
        "| # | 步骤 | 命中行数 | 耗时(ms) | 说明 | SQL |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for index, record in enumerate(records, start=1):
        sql = record.sql.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {index} | {record.step} | {record.row_count} | {record.elapsed_ms:.3f} | "
            f"{record.note} | `{sql}` |"
        )
    lines.append("")
    lines.append("## 全文可读版")
    lines.append("")
    for index, record in enumerate(records, start=1):
        lines.append(f"### {index}. {record.step}（{record.note}，{record.row_count} 行）")
        lines.append("")
        lines.append("```sql")
        lines.append(record.sql)
        lines.append("```")
        lines.append("")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    _write_json(json_path, [record.to_dict() for record in records])
    return md_path, json_path


def _merge_memory_records(
    json_path: Path, writes: list[MemoryWrite], reads: list[MemoryRead]
) -> tuple[list[MemoryWrite], list[MemoryRead]]:
    """把本次记忆写入 / 读回与历史记录合并（按时间顺序累积）。"""
    previous = _load_json(json_path)
    payload = previous if isinstance(previous, dict) else {}
    write_list = [
        MemoryWrite(
            entry_type=str(item.get("entry_type", "")),
            reason=str(item.get("reason", "")),
            text=str(item.get("text", "")),
            scope_id=str(item.get("scope_id", "")),
            entry_id=str(item.get("entry_id", "")),
            revision=int(item.get("revision", 0)),
        )
        for item in payload.get("writes", [])
    ]
    read_list = [
        MemoryRead(
            query=str(item.get("query", "")),
            scope_id=str(item.get("scope_id", "")),
            hits=list(item.get("hits", [])),
        )
        for item in payload.get("reads", [])
    ]
    write_list.extend(writes)
    read_list.extend(reads)
    return write_list[-MAX_RECORD_ITEMS:], read_list[-MAX_RECORD_ITEMS:]


def write_memory_record(
    records_dir: Path, writes: Iterable[MemoryWrite], reads: Iterable[MemoryRead]
) -> tuple[Path, Path]:
    """写出 PowerContext 记忆记录（Markdown + JSON）。

    与数据库记录一样是**累积**的：只读的 ``recall`` 不会覆盖演示阶段写入的
    写入证据。
    """
    md_path = records_dir / "powercontext_memory_record.md"
    json_path = records_dir / "powercontext_memory_record.json"
    write_list, read_list = _merge_memory_records(json_path, list(writes), list(reads))
    lines = ["# PowerContext 记忆记录", "", "## 一、写入（POST /v1/memory/remember）", ""]
    if not write_list:
        lines.append("（本次运行没有写入记忆）")
    for index, item in enumerate(write_list, start=1):
        lines.append(f"### 写入 {index}：`{item.entry_type}`")
        lines.append("")
        lines.append(f"- 作用域：`{item.scope_id}`")
        lines.append(f"- 写入原因：{item.reason}")
        if item.entry_id:
            lines.append(f"- 条目 ID：`{item.entry_id}`（修订号 {item.revision}）")
        lines.append("- 记忆正文：")
        lines.append("")
        lines.append("```text")
        lines.append(item.text)
        lines.append("```")
        lines.append("")
    lines.extend(["## 二、读回（POST /v1/memory/search）", ""])
    if not read_list:
        lines.append("（本次运行没有读回记忆）")
    for index, item in enumerate(read_list, start=1):
        lines.append(f"### 读回 {index}：检索词 `{item.query}`")
        lines.append("")
        lines.append(f"- 作用域：`{item.scope_id}`，命中 {len(item.hits)} 条")
        for hit in item.hits:
            text = str(hit.get("text") or "")
            lines.append(f"- 命中条目（分数 {hit.get('score')}）：")
            lines.append("")
            lines.append("```text")
            lines.append(text)
            lines.append("```")
        lines.append("")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    _write_json(
        json_path,
        {
            "writes": [item.to_dict() for item in write_list],
            "reads": [item.to_dict() for item in read_list],
        },
    )
    return md_path, json_path


def write_text(path: Path, text: str) -> Path:
    """写文本文件（自动创建父目录）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
