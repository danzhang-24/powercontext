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
"""seekdb 存储层：导入的数据必须能原样查回来。"""

from __future__ import annotations

from pathlib import Path

from sddctx.materials import import_materials
from sddctx.store import SeekdbStore


def test_imported_rows_can_be_queried(project_dir: Path, tmp_path: Path) -> None:
    with SeekdbStore(db_dir=tmp_path / "seekdb") as store:
        store.create_schema()
        report = import_materials(store, project_dir)

        assert report.spec_count == 4
        assert report.code_symbol_count >= 7
        assert report.test_case_count == 10

        rows = store.query(
            "SELECT spec_id, status, source_path FROM spec_entry ORDER BY spec_id",
            ("spec_id", "status", "source_path"),
        )
        assert [row["spec_id"] for row in rows] == [
            "SPEC-DISC-001",
            "SPEC-DISC-002",
            "SPEC-DISC-003",
            "SPEC-DISC-004",
        ]
        pending = [row for row in rows if row["status"] == "待实现"]
        assert {row["spec_id"] for row in pending} == {"SPEC-DISC-002", "SPEC-DISC-003"}


def test_query_log_records_sql(project_dir: Path, tmp_path: Path) -> None:
    with SeekdbStore(db_dir=tmp_path / "seekdb") as store:
        store.create_schema()
        import_materials(store, project_dir)
        store.insert_query_log("T-1", "规格检索", "SELECT 1", 3, "2026-10-28T00:00:00+00:00")
        store.commit()
        logs = store.fetch_query_log("T-1")
        assert len(logs) == 1
        assert logs[0]["purpose"] == "规格检索"
        assert logs[0]["row_count"] == 3
