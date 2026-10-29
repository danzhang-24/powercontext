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
"""把演示工程当前状态存成快照，并生成快照之间的 unified diff。

快照是"修改前后代码快照"这一验收材料的来源：``before`` 是初始状态，
``after`` 是 MiniMax 改码后的状态，两者之间的差异即最终提交的代码差异。
"""

from __future__ import annotations

import difflib
import shutil
from pathlib import Path

from .reset import SNAPSHOT_MAP


def capture_snapshot(project_dir: Path, name: str) -> list[str]:
    """把工程当前状态存入 ``snapshots/<name>/``，返回存入的文件列表。"""
    project_dir = Path(project_dir).resolve()
    target_root = project_dir / "snapshots" / name
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    captured: list[str] = []
    for project_rel, snapshot_rel in SNAPSHOT_MAP:
        source = project_dir / project_rel
        if not source.exists():
            raise FileNotFoundError(f"工程缺少 {project_rel}，无法生成快照")
        target = target_root / snapshot_rel
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        captured.append(project_rel)
    return captured


def snapshot_diff(project_dir: Path, before: str = "before", after: str = "after") -> str:
    """生成两个快照之间的 unified diff。"""
    project_dir = Path(project_dir).resolve()
    before_root = project_dir / "snapshots" / before
    after_root = project_dir / "snapshots" / after
    chunks: list[str] = []
    for project_rel, snapshot_rel in SNAPSHOT_MAP:
        old_file = before_root / snapshot_rel
        new_file = after_root / snapshot_rel
        if not old_file.exists() or not new_file.exists():
            continue
        if old_file.is_dir():
            for path in sorted(old_file.rglob("*.py")):
                relative = path.relative_to(before_root).as_posix()
                chunks.append(_diff_file(relative, path, after_root / relative))
        else:
            chunks.append(_diff_file(project_rel, old_file, new_file))
    return "".join(chunk for chunk in chunks if chunk)


def _diff_file(relative: str, old_file: Path, new_file: Path) -> str:
    """生成单个文件的 unified diff。"""
    old_lines = old_file.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = new_file.read_text(encoding="utf-8").splitlines(keepends=True)
    if old_lines == new_lines:
        return ""
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{relative}",
        tofile=f"b/{relative}",
        n=3,
    )
    return "".join(diff)
