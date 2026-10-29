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
"""重置与快照：保证"修改前后使用同一组测试"。

这些用例只在临时目录里操作项目副本，不会影响演示工程的真实状态。
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

from sddctx.reset import reset_project
from sddctx.snapshot import capture_snapshot, snapshot_diff


def _copy_project(project_dir: Path, tmp_path: Path) -> Path:
    """复制一份演示工程到临时目录。"""
    target = tmp_path / "project"
    shutil.copytree(project_dir, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return target


def test_reset_restores_before_snapshot(project_dir: Path, tmp_path: Path) -> None:
    work = _copy_project(project_dir, tmp_path)
    (work / "src" / "order_discount" / "engine.py").write_text("# 被改坏了\n", encoding="utf-8")
    (work / "tests" / "test_order_discount.py").write_text("# 测试也被改了\n", encoding="utf-8")

    restored = reset_project(work)
    assert "src" in restored and "tests" in restored

    pairs = (
        ("src/order_discount/engine.py", "src/order_discount/engine.py"),
        ("src/order_discount/models.py", "src/order_discount/models.py"),
        ("tests/test_order_discount.py", "tests/test_order_discount.py"),
        ("pytest.ini", "pytest.ini"),
        ("specs/order_discount.spec.md", "order_discount.spec.md"),
    )
    for project_rel, snapshot_rel in pairs:
        assert filecmp.cmp(
            work / project_rel,
            work / "snapshots" / "before" / snapshot_rel,
            shallow=False,
        ), project_rel


def test_reset_removes_generated_artifacts(project_dir: Path, tmp_path: Path) -> None:
    work = _copy_project(project_dir, tmp_path)
    (work / "patches").mkdir(exist_ok=True)
    (work / "patches" / "T-1.patch").write_text("diff\n", encoding="utf-8")
    (work / "logs").mkdir(exist_ok=True)
    (work / "logs" / "after-target.log").write_text("log\n", encoding="utf-8")

    reset_project(work)
    assert not (work / "patches" / "T-1.patch").exists()
    assert not (work / "logs").exists()


def test_snapshot_diff_captures_the_code_change(project_dir: Path, tmp_path: Path) -> None:
    work = _copy_project(project_dir, tmp_path)
    capture_snapshot(work, "before")
    capture_snapshot(work, "after")
    diff = snapshot_diff(work, before="before", after="after")
    assert diff == ""  # 同一状态下没有差异

    engine = work / "src" / "order_discount" / "engine.py"
    engine.write_text(engine.read_text(encoding="utf-8") + "\n# 新增一行\n", encoding="utf-8")
    capture_snapshot(work, "after")
    diff = snapshot_diff(work, before="before", after="after")
    assert "新增一行" in diff
    assert "a/src/order_discount/engine.py" in diff
