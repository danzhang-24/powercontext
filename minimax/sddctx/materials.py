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
"""把规格、代码与测试资料导入 seekdb。

导入过程只读取真实文件，所有条目都带有可核对的来源（路径 + 行号）。
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import SeekdbStore

#: 规格条目字段与中文标签的对应关系。
_SPEC_FIELDS = {
    "优先级": "priority",
    "状态": "status",
    "规则": "rule",
    "来源": "source",
    "验收": "acceptance",
}

#: 规格编号与标题的分隔格式：``## SPEC-DISC-001 满减阶梯``。
_SPEC_HEADING = re.compile(r"^##\s+(?P<spec_id>[A-Za-z0-9_.-]+)\s+(?P<title>.+?)\s*$")


@dataclass
class ImportReport:
    """一次导入的结果统计。"""

    spec_count: int = 0
    code_symbol_count: int = 0
    test_case_count: int = 0
    spec_files: list[str] = field(default_factory=list)
    code_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_entries": self.spec_count,
            "code_symbols": self.code_symbol_count,
            "test_cases": self.test_case_count,
            "spec_files": self.spec_files,
            "code_files": self.code_files,
            "test_files": self.test_files,
        }


def import_materials(store: SeekdbStore, project_dir: Path) -> ImportReport:
    """导入演示工程（或任意工程）的规格、代码符号与测试用例。"""
    project_dir = Path(project_dir).resolve()
    report = ImportReport()

    code_rows, code_files = _collect_code(project_dir)
    test_rows, test_files = _collect_tests(project_dir)
    spec_rows, spec_files = _collect_specs(project_dir, code_rows)

    store.replace_code_symbols(code_rows)
    store.replace_test_cases(test_rows)
    for row in spec_rows:
        store.upsert_spec(row)
    store.commit()

    report.code_symbol_count = len(code_rows)
    report.test_case_count = len(test_rows)
    report.spec_count = len(spec_rows)
    report.code_files = code_files
    report.test_files = test_files
    report.spec_files = spec_files
    return report


# --------------------------------------------------------------------------
# 代码
# --------------------------------------------------------------------------


def _collect_code(project_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """解析 src 下的 Python 文件，抽取函数、类与模块级常量。"""
    rows: list[dict[str, Any]] = []
    files: list[str] = []
    src_root = project_dir / "src"
    if not src_root.is_dir():
        return rows, files

    for path in sorted(src_root.rglob("*.py")):
        relative = path.relative_to(project_dir).as_posix()
        files.append(relative)
        rows.extend(parse_code_file(path, relative))
    return rows, files


def parse_code_file(path: Path, relative: str | None = None) -> list[dict[str, Any]]:
    """解析单个 Python 文件，抽取函数、类与模块级常量。"""
    path = Path(path)
    relative = relative or path.name
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover - 输入异常时直接报错
        raise ValueError(f"解析 {relative} 失败: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rows.append(_symbol_row(relative, node.name, "function", node, lines))
        elif isinstance(node, ast.ClassDef):
            rows.append(_symbol_row(relative, node.name, "class", node, lines))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    rows.append(
                        _symbol_row(relative, f"{node.name}.{child.name}", "method", child, lines)
                    )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    rows.append(_symbol_row(relative, target.id, "constant", node, lines))
    return rows


def _symbol_row(
    relative: str,
    symbol: str,
    kind: str,
    node: ast.AST,
    lines: list[str],
) -> dict[str, Any]:
    """把一个 AST 节点转成可入库的代码符号记录。"""
    start = int(getattr(node, "lineno", 0))
    end = int(getattr(node, "end_lineno", start))
    body = "\n".join(lines[start - 1 : end])
    signature = body.splitlines()[0].strip() if body else symbol
    doc = ""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        doc = ast.get_docstring(node) or ""
    return {
        "path": relative,
        "symbol": symbol,
        "kind": kind,
        "line_start": start,
        "line_end": end,
        "signature": signature[:500],
        "doc": doc,
        "body": body,
    }


# --------------------------------------------------------------------------
# 测试
# --------------------------------------------------------------------------


def _collect_tests(project_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """解析 tests 下的测试文件，抽取用例名、标记与行号。"""
    rows: list[dict[str, Any]] = []
    files: list[str] = []
    tests_root = project_dir / "tests"
    if not tests_root.is_dir():
        return rows, files

    for path in sorted(tests_root.rglob("test_*.py")):
        relative = path.relative_to(project_dir).as_posix()
        files.append(relative)
        rows.extend(parse_test_file(path, relative))
    return rows, files


def parse_test_file(path: Path, relative: str | None = None) -> list[dict[str, Any]]:
    """解析单个测试文件，抽取用例名、标记与行号。"""
    path = Path(path)
    relative = relative or path.name
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    rows: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        rows.append(
            {
                "path": relative,
                "name": node.name,
                "marker": _pytest_marker(node),
                "doc": (ast.get_docstring(node) or "").strip(),
                "line_start": int(node.lineno),
                "line_end": int(node.end_lineno or node.lineno),
            }
        )
    return rows


def _pytest_marker(node: ast.AST) -> str:
    """读取测试函数上的 pytest 标记（target / regression）。"""
    for decorator in getattr(node, "decorator_list", []):
        target = decorator
        if isinstance(target, ast.Call):
            target = target.func
        if not isinstance(target, ast.Attribute):
            continue
        if target.attr in {"target", "regression"}:
            return target.attr
    return "unmarked"


# --------------------------------------------------------------------------
# 规格
# --------------------------------------------------------------------------


def _collect_specs(
    project_dir: Path,
    code_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """解析 Markdown 规格文件，取出每条规格及其真实来源位置。"""
    rows: list[dict[str, Any]] = []
    files: list[str] = []
    specs_root = project_dir / "specs"
    if not specs_root.is_dir():
        return rows, files

    for path in sorted(specs_root.rglob("*.md")):
        relative = path.relative_to(project_dir).as_posix()
        files.append(relative)
        rows.extend(parse_spec_file(path, project_dir, code_rows))
    return rows, files


def parse_spec_file(
    path: Path,
    project_dir: Path,
    code_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """解析单个规格文件，返回规格条目列表。

    ``来源`` 字段指向的文件必须真实存在，否则直接报错，避免上下文里出现假来源。
    """
    path = Path(path)
    project_dir = Path(project_dir).resolve()
    relative = path.relative_to(project_dir).as_posix()
    code_index = {(row["path"], row["symbol"]): row for row in (code_rows or [])}

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows: list[dict[str, Any]] = []
    for heading in _iter_sections(lines):
        spec_id = heading["spec_id"]
        fields = heading["fields"]
        source_text = fields.get("source", "")
        source_path, source_symbol = _split_source(source_text)
        symbol_row = code_index.get((source_path, source_symbol))
        if symbol_row is None and source_path:
            symbol_row = next((row for row in (code_rows or []) if row["path"] == source_path), None)
        if source_path and not (project_dir / source_path).is_file():
            raise FileNotFoundError(f"规格 {spec_id} 指向的来源文件不存在: {source_path}")
        rows.append(
            {
                "spec_id": spec_id,
                "title": heading["title"],
                "priority": fields.get("priority", "P2"),
                "status": fields.get("status", "未标注"),
                "rule": fields.get("rule", ""),
                "acceptance": fields.get("acceptance", ""),
                "source_path": source_path,
                "source_symbol": source_symbol,
                "source_line_start": int(symbol_row["line_start"]) if symbol_row else 0,
                "source_line_end": int(symbol_row["line_end"]) if symbol_row else 0,
                "doc_path": relative,
                "doc_line_start": heading["line_start"],
                "doc_line_end": heading["line_end"],
                "updated_at": now,
            }
        )
    return rows


def _iter_sections(lines: list[str]) -> list[dict[str, Any]]:
    """把 Markdown 拆成规格小节。"""
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for number, line in enumerate(lines, start=1):
        match = _SPEC_HEADING.match(line)
        if match:
            if current:
                sections.append(current)
            current = {
                "spec_id": match.group("spec_id"),
                "title": match.group("title"),
                "line_start": number,
                "line_end": number,
                "fields": {},
            }
            continue
        if current is None:
            continue
        current["line_end"] = number
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        label, _, value = stripped[2:].partition(":")
        key = _SPEC_FIELDS.get(label.strip())
        if key:
            current["fields"][key] = value.strip()
    if current:
        sections.append(current)
    return sections


def _split_source(source_text: str) -> tuple[str, str]:
    """把 ``path::symbol`` 拆成路径与符号。"""
    if not source_text:
        return "", ""
    path, _, symbol = source_text.partition("::")
    return path.strip(), symbol.strip()
