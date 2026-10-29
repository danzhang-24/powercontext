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
"""检索：从 seekdb 里取出与任务相关的规格、代码与测试。

检索分两步：

1. 用任务描述切出检索词，在 seekdb 上跑打分 SQL（LIKE 打分 + 全文索引 MATCH），
   得到候选规格条目、代码符号与测试用例。
2. 用规格条目声明的"来源 / 验收"字段做精确回链，补齐真正要改的符号与
   要跑的测试。

所有 SQL 都会写入 ``query_log`` 表，作为数据库参与上下文构造的记录。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .context import (
    CodeRef,
    ContextBundle,
    QueryRecord,
    SpecRef,
    StateView,
    TestRef,
)
from .store import (
    CODE_COLUMNS,
    SPEC_COLUMNS,
    TEST_COLUMNS,
    SeekdbStore,
    quote,
)

#: 检索词上限。
MAX_TERMS = 18

#: 停用词（高频但无区分度的中文/英文词）。
_STOPWORDS = {
    "的",
    "了",
    "和",
    "与",
    "并",
    "在",
    "让",
    "把",
    "使",
    "使",
    "使",
    "按",
    "中",
    "一个",
    "this",
    "that",
    "with",
    "from",
    "the",
    "and",
}

_ASCII_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_CJK_RUN = re.compile(r"[一-鿿]+")
_SPEC_ID = re.compile(r"SPEC-[A-Za-z0-9_.-]+")


def extract_terms(task_text: str) -> list[str]:
    """把任务描述切成检索词。

    中文按 2~3 元组切分（与 seekdb ngram 分词器一致），英文按标识符切分。
    """
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        if len(term) < 2 or term in _STOPWORDS or term in seen:
            return
        seen.add(term)
        terms.append(term)

    for token in _ASCII_TOKEN.findall(task_text):
        add(token.lower())

    for run in _CJK_RUN.findall(task_text):
        if len(run) == 2:
            add(run)
            continue
        for size in (3, 2):
            for index in range(len(run) - size + 1):
                gram = run[index : index + size]
                add(gram)
                if len(terms) >= MAX_TERMS * 2:
                    break
            if len(terms) >= MAX_TERMS * 2:
                break

    # 出现次数多的词更有区分度，但长词（3 元组）更精确，两者都要保留。
    order = {term: index for index, term in enumerate(terms)}
    terms.sort(key=lambda term: (-len(term), order[term]))
    return terms[:MAX_TERMS]


def _haystack(fields: Iterable[str]) -> str:
    """把若干字段拼成一个可 LIKE 的表达式。"""
    return "CONCAT_WS(' ', {})".format(", ".join(fields))


def _like_clause(terms: Iterable[str], fields: Iterable[str]) -> str:
    """构造 LIKE 命中条件。"""
    haystack = _haystack(fields)
    clauses = [f"{haystack} LIKE {quote(f'%{term}%')}" for term in terms]
    return " OR ".join(clauses)


def _score_expression(terms: Iterable[str], fields: Iterable[str], weight: int) -> str:
    """构造打分表达式：命中的检索词越多分越高。"""
    haystack = _haystack(fields)
    parts = [
        f"CASE WHEN {haystack} LIKE {quote(f'%{term}%')} THEN {weight} ELSE 0 END"
        for term in terms
    ]
    return " + ".join(parts) if parts else "0"


def _matched_terms(row: dict[str, Any], terms: Iterable[str], fields: Iterable[str]) -> list[str]:
    """返回该行命中的检索词。"""
    hits: list[str] = []
    for term in terms:
        for field in fields:
            value = row.get(field)
            if value and term in str(value).lower():
                hits.append(term)
                break
    return hits


# --------------------------------------------------------------------------
# 规格
# --------------------------------------------------------------------------


def retrieve_specs(
    store: SeekdbStore,
    task_text: str,
    explicit_ids: list[str],
) -> tuple[list[SpecRef], list[QueryRecord]]:
    """检索规格条目。"""
    terms = extract_terms(task_text)
    records: list[QueryRecord] = []
    scored: dict[str, dict[str, Any]] = {}

    if terms:
        where = _like_clause(terms, ("title", "rule", "acceptance"))
        score = _score_expression(terms, ("title", "rule", "acceptance"), 6)
        sql = (
            "SELECT spec_id, title, priority, status, rule, acceptance, source_path, source_symbol, "
            "source_line_start, source_line_end, doc_path, doc_line_start, doc_line_end, "
            f"{score} AS score FROM spec_entry WHERE {where} ORDER BY score DESC, spec_id LIMIT 25"
        )
        rows = store.query(sql, (*SPEC_COLUMNS, "score"))
        for row in rows:
            row["score"] = float(row.get("score") or 0)
            row["matched"] = _matched_terms(row, terms, ("title", "rule", "acceptance"))
            scored[row["spec_id"]] = row
        records.append(QueryRecord("规格检索（seekdb 打分查询）", sql, len(rows)))

        # 全文索引检索：同一份资料换一种索引方式召回，取并集。
        fts_sql = (
            "SELECT spec_id, title, priority, status, rule, acceptance, source_path, source_symbol, "
            "source_line_start, source_line_end, doc_path, doc_line_start, doc_line_end "
            "FROM spec_entry WHERE MATCH(title, rule) AGAINST ("
            f"{quote(task_text)} IN NATURAL LANGUAGE MODE) LIMIT 25"
        )
        try:
            fts_rows = store.query(fts_sql, SPEC_COLUMNS)
        except Exception:  # noqa: BLE001 - 全文索引不可用时退回打分查询
            fts_rows = []
        for row in fts_rows:
            existing = scored.get(row["spec_id"])
            if existing is None:
                row["score"] = 3.0
                row["matched"] = []
                scored[row["spec_id"]] = row
            else:
                existing["score"] = float(existing.get("score") or 0) + 3.0
        records.append(QueryRecord("规格检索（seekdb 全文索引 MATCH）", fts_sql, len(fts_rows)))

    # 任务里直接点名规格编号时，精确取回。
    if explicit_ids:
        sql = (
            "SELECT spec_id, title, priority, status, rule, acceptance, source_path, source_symbol, "
            "source_line_start, source_line_end, doc_path, doc_line_start, doc_line_end "
            f"FROM spec_entry WHERE spec_id IN ({', '.join(quote(item) for item in explicit_ids)})"
        )
        rows = store.query(sql, SPEC_COLUMNS)
        for row in rows:
            existing = scored.get(row["spec_id"])
            if existing is None:
                row["score"] = 10.0
                row["matched"] = []
                scored[row["spec_id"]] = row
            else:
                existing["score"] = float(existing.get("score") or 0) + 10.0
        records.append(QueryRecord("规格精确取回（任务点名）", sql, len(rows)))

    specs = [
        SpecRef(
            spec_id=row["spec_id"],
            title=row["title"],
            priority=row["priority"],
            status=row["status"],
            rule=row["rule"],
            acceptance=[item.strip() for item in str(row.get("acceptance") or "").split(",") if item.strip()],
            source_path=row.get("source_path") or "",
            source_symbol=row.get("source_symbol") or "",
            source_line_start=int(row.get("source_line_start") or 0),
            source_line_end=int(row.get("source_line_end") or 0),
            doc_path=row.get("doc_path") or "",
            doc_line_start=int(row.get("doc_line_start") or 0),
            doc_line_end=int(row.get("doc_line_end") or 0),
            score=float(row.get("score") or 0),
            matched_terms=list(row.get("matched") or []),
        )
        for row in scored.values()
    ]
    specs.sort(key=lambda item: (-item.score, item.spec_id))
    return specs, records


# --------------------------------------------------------------------------
# 代码与测试
# --------------------------------------------------------------------------


def retrieve_code(
    store: SeekdbStore,
    project_dir: Path,
    specs: list[SpecRef],
    terms: list[str],
) -> tuple[list[CodeRef], list[QueryRecord]]:
    """检索需要修改的代码文件或符号。"""
    records: list[QueryRecord] = []
    refs: list[CodeRef] = []
    seen: set[tuple[str, str]] = set()

    # 1) 规格声明的实现位置，精确回链。
    linked: list[tuple[str, str, str]] = []
    for spec in specs:
        if not spec.source_path:
            continue
        linked.append((spec.source_path, spec.source_symbol, spec.spec_id))
    if linked:
        sql = (
            "SELECT path, symbol, kind, line_start, line_end, signature, doc, body FROM code_symbol WHERE path IN ("
            + ", ".join(quote(item) for item in sorted({item[0] for item in linked}))
            + ") ORDER BY path, line_start"
        )
        rows = store.query(sql, CODE_COLUMNS)
        records.append(QueryRecord("代码回链（规格来源字段）", sql, len(rows)))
        for path, symbol, spec_id in linked:
            for row in rows:
                if row["path"] != path:
                    continue
                if symbol and row["symbol"] != symbol:
                    continue
                key = (row["path"], row["symbol"])
                if key in seen:
                    continue
                seen.add(key)
                refs.append(
                    CodeRef(
                        path=row["path"],
                        symbol=row["symbol"],
                        kind=row["kind"],
                        line_start=int(row["line_start"]),
                        line_end=int(row["line_end"]),
                        signature=row["signature"],
                        doc=row["doc"],
                        excerpt=_read_excerpt(project_dir, row["path"], int(row["line_start"]), int(row["line_end"])),
                        reason=f"规格 {spec_id} 声明的实现位置",
                        score=100.0,
                    )
                )

    # 2) 关键词召回，作为补充。
    if terms:
        where = _like_clause(terms, ("symbol", "signature", "doc", "body"))
        score = _score_expression(terms, ("symbol", "signature", "doc", "body"), 4)
        sql = (
            "SELECT path, symbol, kind, line_start, line_end, signature, doc, body, "
            f"{score} AS score FROM code_symbol WHERE {where} ORDER BY score DESC, path, line_start LIMIT 20"
        )
        rows = store.query(sql, (*CODE_COLUMNS, "score"))
        records.append(QueryRecord("代码检索（seekdb 打分查询）", sql, len(rows)))
        candidates = []
        for row in rows:
            key = (row["path"], row["symbol"])
            if key in seen:
                continue
            candidates.append(row)
        if candidates:
            top = max(float(row.get("score") or 0) for row in candidates) or 1.0
            for row in candidates:
                value = float(row.get("score") or 0)
                if value < top * 0.4:
                    continue
                key = (row["path"], row["symbol"])
                if key in seen:
                    continue
                seen.add(key)
                refs.append(
                    CodeRef(
                        path=row["path"],
                        symbol=row["symbol"],
                        kind=row["kind"],
                        line_start=int(row["line_start"]),
                        line_end=int(row["line_end"]),
                        signature=row["signature"],
                        doc=row["doc"],
                        excerpt=_read_excerpt(project_dir, row["path"], int(row["line_start"]), int(row["line_end"])),
                        reason="关键词命中：" + ", ".join(
                            _matched_terms(row, terms, ("symbol", "signature", "doc"))
                        ),
                        score=value,
                    )
                )
    return refs, records


def retrieve_tests(
    store: SeekdbStore,
    project_dir: Path,
    specs: list[SpecRef],
    terms: list[str],
) -> tuple[list[TestRef], list[QueryRecord]]:
    """检索用于验证功能及兼容性的测试。"""
    records: list[QueryRecord] = []
    refs: list[TestRef] = []
    seen: set[tuple[str, str]] = set()

    wanted: list[tuple[str, str]] = []
    for spec in specs:
        for name in spec.acceptance:
            wanted.append((spec.spec_id, name))
    if wanted:
        names = [name for _, name in wanted]
        sql = (
            "SELECT path, name, marker, doc, line_start, line_end FROM test_case WHERE name IN ("
            + ", ".join(quote(item) for item in names)
            + ") ORDER BY path, line_start"
        )
        rows = store.query(sql, TEST_COLUMNS)
        records.append(QueryRecord("测试回链（规格验收字段）", sql, len(rows)))
        by_name = {row["name"]: row for row in rows}
        for spec_id, name in wanted:
            row = by_name.get(name)
            if row is None:
                continue
            key = (row["path"], row["name"])
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                TestRef(
                    path=row["path"],
                    name=row["name"],
                    marker=row["marker"],
                    line_start=int(row["line_start"]),
                    line_end=int(row["line_end"]),
                    doc=row["doc"],
                    excerpt=_read_excerpt(project_dir, row["path"], int(row["line_start"]), int(row["line_end"])),
                    reason=f"规格 {spec_id} 声明的验收测试",
                    score=100.0,
                )
            )

    if terms:
        where = _like_clause(terms, ("name", "doc"))
        score = _score_expression(terms, ("name", "doc"), 6)
        sql = (
            "SELECT path, name, marker, doc, line_start, line_end, "
            f"{score} AS score FROM test_case WHERE {where} ORDER BY score DESC, path, line_start LIMIT 20"
        )
        rows = store.query(sql, (*TEST_COLUMNS, "score"))
        records.append(QueryRecord("测试检索（seekdb 打分查询）", sql, len(rows)))
        for row in rows:
            key = (row["path"], row["name"])
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                TestRef(
                    path=row["path"],
                    name=row["name"],
                    marker=row["marker"],
                    line_start=int(row["line_start"]),
                    line_end=int(row["line_end"]),
                    doc=row["doc"],
                    excerpt=_read_excerpt(project_dir, row["path"], int(row["line_start"]), int(row["line_end"])),
                    reason="关键词命中：" + ", ".join(_matched_terms(row, terms, ("name", "doc"))),
                    score=float(row.get("score") or 0),
                )
            )
    return refs, records


def _read_excerpt(project_dir: Path, relative: str, line_start: int, line_end: int) -> str:
    """读取文件里指定行范围的真实内容。"""
    path = project_dir / relative
    if not path.is_file():
        raise FileNotFoundError(f"上下文来源不存在: {relative}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_start <= 0:
        return ""
    start = max(line_start - 1, 0)
    end = min(line_end, len(lines))
    return "\n".join(lines[start:end])


# --------------------------------------------------------------------------
# 组合
# --------------------------------------------------------------------------


def build_context(
    store: SeekdbStore,
    project_dir: Path,
    task_id: str,
    task_text: str,
    state: StateView | None = None,
) -> ContextBundle:
    """检索并组装完整开发上下文。"""
    project_dir = Path(project_dir).resolve()
    terms = extract_terms(task_text)
    explicit_ids = sorted(set(_SPEC_ID.findall(task_text)))

    specs, records = retrieve_specs(store, task_text, explicit_ids)
    code, code_records = retrieve_code(store, project_dir, specs, terms)
    tests, test_records = retrieve_tests(store, project_dir, specs, terms)
    records.extend(code_records)
    records.extend(test_records)

    bundle = ContextBundle(
        task_id=task_id,
        task_text=task_text,
        project_dir=str(project_dir),
        specs=specs,
        code=code,
        tests=tests,
        state=state or StateView(scope_id=""),
        queries=records,
        terms=terms,
    )
    return bundle
