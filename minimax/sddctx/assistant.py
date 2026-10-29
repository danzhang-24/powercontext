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
"""把上下文交给 MiniMax，拿到补丁并应用。

补丁解析与应用在本地完成，不依赖外部 diff 工具，避免干净环境里缺少依赖。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .context import ContextBundle
from .minimax_client import ChatResult, MiniMaxClient

#: 从模型回复里提取 diff 的代码块。
_DIFF_BLOCK = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.S)

#: unified diff 的文件头。
_FILE_HEADER = re.compile(r"^---\s+(?P<old>\S+)(?:\s+(?P<old_time>.*))?$")

_INSTRUCTIONS = """
# 输出要求

1. 严格按照上面给出的规格条目修改代码，只实现规格里"状态"为待实现的条目。
2. 不要修改测试文件，不要新增测试文件，不要修改规格文件。
3. 只修改上下文里列出的文件与符号；如确实需要改动其它文件，在补丁前用一行文字说明原因。
4. 输出一个 unified diff，路径相对于工程根目录，格式如下：

```diff
diff --git a/src/order_discount/engine.py b/src/order_discount/engine.py
--- a/src/order_discount/engine.py
+++ b/src/order_discount/engine.py
@@ -21,7 +21,12 @@
 ...
```

5. 除补丁外不要输出其它内容。
""".strip()


@dataclass
class AssistantResult:
    """一次"上下文 → 模型 → 补丁"的过程记录。"""

    task_id: str
    prompt: str
    response: str
    diff: str
    model: str
    transport: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    applied_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model": self.model,
            "transport": self.transport,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "prompt": self.prompt,
            "response": self.response,
            "diff": self.diff,
            "applied_files": self.applied_files,
        }


def build_prompt(bundle: ContextBundle) -> str:
    """把上下文拼成给 MiniMax 的提示词。"""
    return f"{bundle.to_prompt()}\n\n{_INSTRUCTIONS}"


def extract_diff(text: str) -> str:
    """从模型回复里提取 unified diff。"""
    blocks = _DIFF_BLOCK.findall(text or "")
    for block in blocks:
        if "--- " in block and "+++ " in block:
            return block.strip() + "\n"
    # 没有代码块时，退回直接找 diff 头。
    lines = (text or "").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("--- "):
            start = index
            break
    if start is None:
        return ""
    return "\n".join(lines[start:]).strip() + "\n"


def run_assistant(
    bundle: ContextBundle,
    client: MiniMaxClient,
    apply_patch: bool = True,
) -> AssistantResult:
    """请求 MiniMax 产出补丁并（可选）直接应用。"""
    prompt = build_prompt(bundle)
    chat: ChatResult = client.chat(prompt)
    diff = extract_diff(chat.content)
    applied: list[str] = []
    if apply_patch and diff:
        try:
            applied = apply_unified_diff(Path(bundle.project_dir), diff)
        except ValueError as exc:
            # 同一个补丁重复应用时，上下文一定对不上。与其丢一个看不懂的
            # "上下文不匹配"，不如告诉调用方大概该怎么办。
            if _patch_already_applied(Path(bundle.project_dir), diff):
                raise ValueError(
                    f"{exc}\n"
                    "看起来这个补丁已经应用过了（重复执行）。可以先重置工程再跑：\n"
                    "  python -m sddctx reset\n"
                    "  python -m sddctx demo --reset ...\n"
                    "或者加 --skip-apply 只做检索与验证。"
                ) from exc
            raise
    return AssistantResult(
        task_id=bundle.task_id,
        prompt=prompt,
        response=chat.content,
        diff=diff,
        model=chat.model,
        transport=chat.transport,
        usage=chat.usage,
        latency_ms=chat.latency_ms,
        applied_files=applied,
    )


# --------------------------------------------------------------------------
# 补丁应用
# --------------------------------------------------------------------------


@dataclass
class _Hunk:
    old_start: int
    old_lines: list[str]
    new_lines: list[str]



def _patch_already_applied(project_dir: Path, diff_text: str) -> bool:
    """判断补丁的新增内容是否已经出现在目标文件里。"""
    files = _parse_diff(diff_text)
    for relative, hunks in files.items():
        target = project_dir / relative
        if not target.is_file():
            continue
        content = target.read_text(encoding="utf-8")
        for hunk in hunks:
            added = [line[1:] for line in hunk.lines if line.startswith("+")]
            if added and all(line in content for line in added):
                return True
    return False


def apply_unified_diff(project_dir: Path, diff_text: str) -> list[str]:
    """应用 unified diff，返回被修改的文件列表。"""
    files = _parse_diff(diff_text)
    changed: list[str] = []
    for relative, hunks in files.items():
        target = project_dir / relative
        if not target.is_file():
            raise FileNotFoundError(f"补丁指向的文件不存在: {relative}")
        original = target.read_text(encoding="utf-8").splitlines()
        updated = list(original)
        for hunk in hunks:
            _apply_hunk(updated, hunk, relative)
        if updated != original:
            target.write_text("\n".join(updated) + "\n", encoding="utf-8")
            changed.append(relative)
    return changed


def _parse_diff(diff_text: str) -> dict[str, list[_Hunk]]:
    """把 unified diff 解析成 {文件: [hunk]}。"""
    files: dict[str, list[_Hunk]] = {}
    current: str | None = None
    lines = diff_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        header = _FILE_HEADER.match(line)
        if header and index + 1 < len(lines) and lines[index + 1].startswith("+++ "):
            new_path = lines[index + 1][4:].strip().split("\t")[0]
            current = new_path[2:] if new_path.startswith(("a/", "b/")) else new_path
            files.setdefault(current, [])
            index += 2
            continue
        if line.startswith("@@") and current is not None:
            match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not match:
                raise ValueError(f"无法解析 hunk 头: {line}")
            old_start = int(match.group(1))
            old_lines: list[str] = []
            new_lines: list[str] = []
            index += 1
            while index < len(lines):
                body = lines[index]
                if body.startswith("@@") or body.startswith("--- ") or body.startswith("diff "):
                    break
                if body.startswith("-"):
                    old_lines.append(body[1:])
                elif body.startswith("+"):
                    new_lines.append(body[1:])
                elif body.startswith(" ") or body == "":
                    old_lines.append(body[1:] if body.startswith(" ") else "")
                    new_lines.append(body[1:] if body.startswith(" ") else "")
                elif body.startswith("\\"):
                    pass
                else:
                    break
                index += 1
            files[current].append(_Hunk(old_start=old_start, old_lines=old_lines, new_lines=new_lines))
            continue
        index += 1
    return files


def _apply_hunk(lines: list[str], hunk: _Hunk, relative: str) -> None:
    """把一个 hunk 应用到行列表上。"""
    expected = hunk.old_start - 1
    position = _locate(lines, hunk.old_lines, expected)
    if position is None:
        raise ValueError(
            f"补丁无法应用到 {relative} 的第 {hunk.old_start} 行附近：上下文不匹配"
        )
    lines[position : position + len(hunk.old_lines)] = hunk.new_lines


def _locate(lines: list[str], old_lines: list[str], expected: int) -> int | None:
    """在期望位置附近找到 old_lines 的落点。"""
    if not old_lines:
        return min(expected, len(lines))
    candidates = [expected]
    for offset in range(1, 60):
        candidates.append(expected + offset)
        candidates.append(expected - offset)
    for start in candidates:
        if start < 0 or start + len(old_lines) > len(lines):
            continue
        if lines[start : start + len(old_lines)] == old_lines:
            return start
    # 兜底：全文查找唯一匹配。
    matches = [
        index
        for index in range(len(lines) - len(old_lines) + 1)
        if lines[index : index + len(old_lines)] == old_lines
    ]
    if len(matches) == 1:
        return matches[0]
    return None
