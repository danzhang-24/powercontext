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
"""资料导入：规格 / 代码 / 测试的解析。"""

from __future__ import annotations

from pathlib import Path

from sddctx.materials import parse_code_file, parse_spec_file, parse_test_file


def test_parse_spec_file_extracts_all_entries(project_dir: Path) -> None:
    specs = parse_spec_file(project_dir / "specs" / "order_discount.spec.md", project_dir)
    ids = [item["spec_id"] for item in specs]
    assert ids == ["SPEC-DISC-001", "SPEC-DISC-002", "SPEC-DISC-003", "SPEC-DISC-004"]


def test_spec_entry_keeps_rule_and_locations(project_dir: Path) -> None:
    specs = parse_spec_file(project_dir / "specs" / "order_discount.spec.md", project_dir)
    entry = next(item for item in specs if item["spec_id"] == "SPEC-DISC-002")
    assert entry["status"] == "待实现"
    assert "商品小计" in entry["rule"]
    assert entry["source_path"] == "src/order_discount/engine.py"
    assert entry["source_symbol"] == "compute_discount"
    assert entry["doc_line_start"] < entry["doc_line_end"]
    assert "test_threshold_ignores_shipping" in entry["acceptance"]


def test_parse_code_file_records_symbols_and_lines(project_dir: Path) -> None:
    relative = "src/order_discount/engine.py"
    symbols = parse_code_file(project_dir / relative, relative)
    names = {item["symbol"] for item in symbols}
    assert {"compute_discount", "MEMBER_DISCOUNT_RATE"} <= names
    compute = next(item for item in symbols if item["symbol"] == "compute_discount")
    assert compute["kind"] == "function"
    assert compute["line_start"] < compute["line_end"]
    assert "def compute_discount(order: Order) -> float:" in compute["signature"]


def test_parse_test_file_detects_markers(project_dir: Path) -> None:
    relative = "tests/test_order_discount.py"
    tests = parse_test_file(project_dir / relative, relative)
    markers = {item["name"]: item["marker"] for item in tests}
    assert markers["test_threshold_ignores_shipping"] == "target"
    assert markers["test_tier_300_subtotal"] == "regression"
    assert len(tests) == 10


def test_spec_source_must_exist(tmp_path: Path, project_dir: Path) -> None:
    """规格指向的来源文件不存在时必须报错，而不是生成假来源。"""
    spec = tmp_path / "specs" / "broken.spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "## SPEC-X 不存在的来源\n\n- 状态: 待实现\n- 规则: 无\n- 来源: src/order_discount/nope.py::x\n",
        encoding="utf-8",
    )
    try:
        parse_spec_file(spec, tmp_path)
    except FileNotFoundError as exc:
        assert "nope.py" in str(exc)
    else:  # pragma: no cover - 断言失败时给出明确信息
        raise AssertionError("来源文件不存在时应当抛出 FileNotFoundError")
