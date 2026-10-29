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
"""把演示工程恢复到"修改前"状态。

快照目录 ``demo_project/snapshots/before`` 保存了修改前的源码、测试与规格，
是"同一组测试在修改前后保持一致"的依据。
"""

from __future__ import annotations

import shutil
from pathlib import Path

#: 快照内容与工程路径的映射：(工程内路径, 快照内路径)。
SNAPSHOT_MAP: tuple[tuple[str, str], ...] = (
    ("src", "src"),
    ("tests", "tests"),
    ("pytest.ini", "pytest.ini"),
    ("specs/order_discount.spec.md", "order_discount.spec.md"),
)


def reset_project(project_dir: Path) -> list[str]:
    """把工程恢复成修改前状态，返回被恢复的路径列表。"""
    project_dir = Path(project_dir).resolve()
    snapshot_dir = project_dir / "snapshots" / "before"
    if not snapshot_dir.is_dir():
        raise FileNotFoundError(f"缺少修改前快照目录：{snapshot_dir}")

    restored: list[str] = []
    for project_rel, snapshot_rel in SNAPSHOT_MAP:
        source = snapshot_dir / snapshot_rel
        target = project_dir / project_rel
        if not source.exists():
            raise FileNotFoundError(f"快照缺少文件：{source}")
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        restored.append(project_rel)

    patches_dir = project_dir / "patches"
    if patches_dir.is_dir():
        for patch in patches_dir.glob("*.patch"):
            patch.unlink()
    shutil.rmtree(project_dir / "logs", ignore_errors=True)

    for cache in list(project_dir.rglob("__pycache__")) + list(project_dir.rglob(".pytest_cache")):
        shutil.rmtree(cache, ignore_errors=True)
    return restored
