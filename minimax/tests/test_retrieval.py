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
"""上下文检索：必须能定位到真实存在的规格、代码与测试。"""

from __future__ import annotations

from pathlib import Path

from sddctx.materials import import_materials
from sddctx.retrieval import build_context, extract_terms
from sddctx.store import SeekdbStore

TASK = "让满减门槛只按商品小计计算，并排除含易碎品的订单"


def _build(project_dir: Path, tmp_path: Path):
    """导入资料并检索上下文。"""
    with SeekdbStore(db_dir=tmp_path / "seekdb") as store:
        store.create_schema()
        import_materials(store, project_dir)
        return build_context(store, project_dir, "T-1", TASK)


def test_extract_terms_splits_chinese_into_ngrams() -> None:
    terms = extract_terms(TASK)
    assert "让满减" in terms
    assert "满减门" in terms
    assert len(terms) <= 18


def test_context_ranks_pending_specs_first(project_dir: Path, tmp_path: Path) -> None:
    bundle = _build(project_dir, tmp_path)
    spec_ids = [item.spec_id for item in bundle.specs]
    assert spec_ids[:2] == ["SPEC-DISC-002", "SPEC-DISC-003"]
    assert "SPEC-DISC-001" in spec_ids


def test_context_points_at_real_files(project_dir: Path, tmp_path: Path) -> None:
    bundle = _build(project_dir, tmp_path)

    for item in bundle.specs:
        assert (project_dir / item.doc_path).is_file()
        assert item.rule
    for item in bundle.code:
        assert (project_dir / item.path).is_file()
        assert item.excerpt
    for item in bundle.tests:
        assert (project_dir / item.path).is_file()
        assert item.excerpt

    symbols = {item.symbol for item in bundle.code}
    assert "compute_discount" in symbols

    test_names = {item.name for item in bundle.tests}
    assert "test_threshold_ignores_shipping" in test_names
    assert "test_tier_300_subtotal" in test_names


def test_context_markdown_has_required_sections(project_dir: Path, tmp_path: Path) -> None:
    bundle = _build(project_dir, tmp_path)
    markdown = bundle.to_markdown()
    for heading in (
        "适用的规格条目",
        "需要修改的代码文件或符号",
        "用于验证功能及兼容性的测试",
        "已有任务状态与验证结果",
        "本次上下文使用的数据库查询",
    ):
        assert heading in markdown


def test_context_records_the_queries_it_ran(project_dir: Path, tmp_path: Path) -> None:
    bundle = _build(project_dir, tmp_path)
    assert bundle.queries
    assert all(record.sql.strip() for record in bundle.queries)
