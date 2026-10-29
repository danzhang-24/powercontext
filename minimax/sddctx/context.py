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
"""上下文数据模型。

上下文必须能定位四类来源：适用的规格条目、需要修改的代码、用于验证的测试、
以及已有任务状态与验证结果。所有来源都带真实路径与行号。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SpecRef:
    """一条规格条目。"""

    spec_id: str
    title: str
    priority: str
    status: str
    rule: str
    acceptance: list[str]
    source_path: str
    source_symbol: str
    source_line_start: int
    source_line_end: int
    doc_path: str
    doc_line_start: int
    doc_line_end: int
    score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)

    @property
    def locator(self) -> str:
        return f"{self.doc_path}:{self.doc_line_start}-{self.doc_line_end}"

    @property
    def code_locator(self) -> str:
        if not self.source_path:
            return ""
        if self.source_line_start:
            return f"{self.source_path}:{self.source_line_start}-{self.source_line_end}"
        return self.source_path

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["locator"] = self.locator
        data["code_locator"] = self.code_locator
        return data


@dataclass
class CodeRef:
    """需要修改的代码文件或符号。"""

    path: str
    symbol: str
    kind: str
    line_start: int
    line_end: int
    signature: str
    doc: str
    excerpt: str
    reason: str = "keyword"
    score: float = 0.0

    @property
    def locator(self) -> str:
        return f"{self.path}:{self.line_start}-{self.line_end}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["locator"] = self.locator
        return data


@dataclass
class TestRef:
    """用于验证功能及兼容性的测试。"""

    path: str
    name: str
    marker: str
    line_start: int
    line_end: int
    doc: str
    excerpt: str
    reason: str = "keyword"
    score: float = 0.0

    @property
    def locator(self) -> str:
        return f"{self.path}:{self.line_start}-{self.line_end}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["locator"] = self.locator
        return data


@dataclass
class VerificationView:
    """一次验证的结论。"""

    phase: str
    suite: str
    command: str
    exit_code: int
    passed: int
    failed: int
    errored: int
    summary: str
    code_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StateView:
    """来自 PowerContext 的任务状态。"""

    scope_id: str
    source: str = "powercontext"
    entries: list[dict[str, Any]] = field(default_factory=list)
    done: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    verifications: list[VerificationView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "source": self.source,
            "entries": self.entries,
            "done": self.done,
            "pending": self.pending,
            "verifications": [item.to_dict() for item in self.verifications],
        }


@dataclass
class QueryRecord:
    """一条用于构造上下文的数据库查询。"""

    purpose: str
    sql: str
    row_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextBundle:
    """一次任务检索得到的完整开发上下文。"""

    task_id: str
    task_text: str
    project_dir: str
    specs: list[SpecRef] = field(default_factory=list)
    code: list[CodeRef] = field(default_factory=list)
    tests: list[TestRef] = field(default_factory=list)
    state: StateView = field(default_factory=lambda: StateView(scope_id=""))
    queries: list[QueryRecord] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task": self.task_text,
            "project_dir": self.project_dir,
            "terms": self.terms,
            "specs": [item.to_dict() for item in self.specs],
            "code": [item.to_dict() for item in self.code],
            "tests": [item.to_dict() for item in self.tests],
            "state": self.state.to_dict(),
            "queries": [item.to_dict() for item in self.queries],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    # -- 人类可读输出 -----------------------------------------------------
    def to_markdown(self) -> str:
        """输出给人看的上下文报告。"""
        lines: list[str] = []
        lines.append(f"# 开发上下文：{self.task_id}")
        lines.append("")
        lines.append(f"- 任务描述：{self.task_text}")
        lines.append(f"- 工程目录：{self.project_dir}")
        lines.append(f"- 检索关键词：{', '.join(self.terms) if self.terms else '（无）'}")
        lines.append("")

        lines.append("## 1. 适用的规格条目")
        if self.specs:
            for item in self.specs:
                lines.append(
                    f"- [{item.spec_id}] {item.title}（优先级 {item.priority}，状态 {item.status}）"
                )
                lines.append(f"  - 规格位置：{item.locator}")
                if item.code_locator:
                    lines.append(f"  - 实现位置：{item.code_locator}")
                lines.append(f"  - 规则：{item.rule}")
                if item.acceptance:
                    lines.append(f"  - 验收测试：{', '.join(item.acceptance)}")
        else:
            lines.append("- （未检索到规格条目）")
        lines.append("")

        lines.append("## 2. 需要修改的代码文件或符号")
        if self.code:
            for item in self.code:
                lines.append(f"- {item.symbol}（{item.kind}）@ {item.locator} — {item.reason}")
                lines.append(f"  - 签名：{item.signature}")
        else:
            lines.append("- （未检索到代码符号）")
        lines.append("")

        lines.append("## 3. 用于验证功能及兼容性的测试")
        if self.tests:
            for item in self.tests:
                lines.append(
                    f"- {item.name} [{item.marker}] @ {item.locator} — {item.reason}"
                )
                if item.doc:
                    lines.append(f"  - 说明：{item.doc}")
        else:
            lines.append("- （未检索到测试）")
        lines.append("")

        lines.append("## 4. 已有任务状态与验证结果")
        lines.append(f"- 状态来源：{self.state.source}（scope: {self.state.scope_id}）")
        if self.state.done:
            lines.append("- 已完成：")
            lines.extend(f"  - {item}" for item in self.state.done)
        else:
            lines.append("- 已完成：（空）")
        if self.state.pending:
            lines.append("- 待办：")
            lines.extend(f"  - {item}" for item in self.state.pending)
        else:
            lines.append("- 待办：（空）")
        if self.state.verifications:
            lines.append("- 已有验证结果：")
            for item in self.state.verifications:
                lines.append(
                    f"  - [{item.phase}/{item.suite}] exit={item.exit_code} "
                    f"passed={item.passed} failed={item.failed} errored={item.errored} — {item.summary}"
                )
        else:
            lines.append("- 已有验证结果：（空）")
        lines.append("")

        lines.append("## 5. 本次上下文使用的数据库查询")
        for index, query in enumerate(self.queries, start=1):
            lines.append(f"{index}. [{query.purpose}] 命中 {query.row_count} 行")
            lines.append("   ```sql")
            lines.append(query.sql.strip())
            lines.append("   ```")
        return "\n".join(lines)

    def to_prompt(self) -> str:
        """输出给 MiniMax 的开发上下文提示词。"""
        parts: list[str] = []
        parts.append("# 开发任务\n" + self.task_text)
        parts.append("# 目标工程\n" + self.project_dir)

        parts.append("# 适用规格条目（来自 seekdb 检索）")
        if self.specs:
            for item in self.specs:
                parts.append(
                    f"- {item.spec_id} {item.title} | 优先级 {item.priority} | 状态 {item.status}\n"
                    f"  规则：{item.rule}\n"
                    f"  规格位置：{item.locator}\n"
                    f"  实现位置：{item.code_locator}"
                )
        else:
            parts.append("（无）")

        parts.append("# 需要修改的代码")
        if self.code:
            for item in self.code:
                parts.append(
                    f"## 文件 {item.path} 符号 {item.symbol} ({item.kind}) 行 {item.line_start}-{item.line_end}\n"
                    f"{item.excerpt}"
                )
        else:
            parts.append("（无）")

        parts.append("# 用于验证的测试")
        if self.tests:
            for item in self.tests:
                parts.append(
                    f"## {item.path}::{item.name} [{item.marker}] 行 {item.line_start}-{item.line_end}\n"
                    f"{item.excerpt}"
                )
        else:
            parts.append("（无）")

        state = self.state
        parts.append("# 当前任务状态")
        parts.append(
            "已完成："
            + ("；".join(state.done) if state.done else "（空）")
            + "\n待办："
            + ("；".join(state.pending) if state.pending else "（空）")
        )
        if state.verifications:
            parts.append(
                "已有验证结果：\n"
                + "\n".join(
                    f"- [{item.phase}/{item.suite}] exit={item.exit_code} "
                    f"passed={item.passed} failed={item.failed} errored={item.errored}"
                    for item in state.verifications
                )
            )
        else:
            parts.append("已有验证结果：（空）")
        return "\n\n".join(parts)
