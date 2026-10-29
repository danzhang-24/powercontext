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
"""补丁解析与应用，以及任务状态的存取格式。"""

from __future__ import annotations

from pathlib import Path

from sddctx.assistant import apply_unified_diff, extract_diff
from sddctx.task_state import TaskState

DIFF = """```diff
diff --git a/src/order_discount/engine.py b/src/order_discount/engine.py
--- a/src/order_discount/engine.py
+++ b/src/order_discount/engine.py
@@ -28,6 +28,8 @@
         优惠金额（元），保留两位小数。
     \"\"\"
-    amount = order.total
+    if any(item.fragile for item in order.items):
+        return 0.0
+    amount = order.subtotal
     discount = 0.0
     for threshold, reduction in DISCOUNT_TIERS:
         if amount >= threshold:
```
"""


def test_extract_diff_from_code_fence() -> None:
    diff = extract_diff(DIFF)
    assert diff.startswith("diff --git")
    assert "-    amount = order.total" in diff


def test_extract_diff_without_fence() -> None:
    plain = "改动如下：\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    diff = extract_diff(plain)
    assert "--- a/x.py" in diff


def test_apply_unified_diff_changes_only_listed_file(tmp_path: Path) -> None:
    target = tmp_path / "src" / "order_discount" / "engine.py"
    target.parent.mkdir(parents=True)
    original = "\n".join(
        [
            "def compute_discount(order):",
            '    """计算订单优惠金额。',
            "",
            "    Returns:",
            "        优惠金额（元），保留两位小数。",
            '    """',
            "    amount = order.total",
            "    discount = 0.0",
            "    for threshold, reduction in DISCOUNT_TIERS:",
            "        if amount >= threshold:",
        ]
    )
    target.write_text(original + "\n", encoding="utf-8")
    changed = apply_unified_diff(tmp_path, extract_diff(DIFF))
    assert changed == ["src/order_discount/engine.py"]
    text = target.read_text(encoding="utf-8")
    assert "if any(item.fragile for item in order.items):" in text
    assert "amount = order.subtotal" in text
    assert "amount = order.total" not in text


def test_apply_unified_diff_rejects_missing_file(tmp_path: Path) -> None:
    try:
        apply_unified_diff(tmp_path, extract_diff(DIFF))
    except FileNotFoundError as exc:
        assert "engine.py" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("补丁指向不存在的文件时应当报错")


def test_task_state_round_trip() -> None:
    state = TaskState(
        task_id="T-1",
        phase="after",
        done=["导入资料"],
        pending=["补充回归用例"],
        verifications=[
            {
                "phase": "before",
                "suite": "target",
                "exit_code": 1,
                "passed": 0,
                "failed": 4,
                "errored": 0,
                "summary": "4 failed, 6 deselected in 0.02s",
                "code_version": "abc123+content:def456",
            }
        ],
        artifacts=["records/minimax_dev_record.md"],
        updated_at="2026-10-28T00:00:00+00:00",
    )
    parsed = TaskState.parse(state.render())
    assert parsed is not None
    assert parsed.task_id == "T-1"
    assert parsed.phase == "after"
    assert parsed.done == ["导入资料"]
    assert parsed.pending == ["补充回归用例"]
    assert parsed.artifacts == ["records/minimax_dev_record.md"]
    assert parsed.verifications[0]["exit_code"] == 1
    assert parsed.verifications[0]["failed"] == 4
    assert parsed.verifications[0]["summary"] == "4 failed, 6 deselected in 0.02s"
    assert parsed.verifications[0]["code_version"] == "abc123+content:def456"


def test_parse_ignores_foreign_memory() -> None:
    assert TaskState.parse("随便一段记忆，不是本模块的状态") is None
