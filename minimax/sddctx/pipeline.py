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
"""流程编排：导入 → 检索上下文 → MiniMax 改码 → 验证 → 保存状态 → 重启复用。

每一步都会把可核对的记录写到 ``records/``，用于提交材料中的"技术使用记录"。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assistant import AssistantResult, run_assistant
from .config import Settings
from .context import ContextBundle
from .materials import ImportReport, import_materials
from .minimax_client import MiniMaxClient
from .retrieval import build_context
from .store import SeekdbStore
from .task_state import PowerContextState, TaskState
from .verifier import SuiteResult, run_suite


def now() -> str:
    """当前时间（UTC，秒精度）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class DemoOutcome:
    """一次端到端演示的结果。"""

    task_id: str
    context: ContextBundle
    assistant: AssistantResult | None
    verifications: list[SuiteResult]
    state_saved: dict[str, Any] | None
    report: ImportReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "context": self.context.to_dict(),
            "assistant": self.assistant.to_dict() if self.assistant else None,
            "verifications": [item.to_dict() for item in self.verifications],
            "state_saved": self.state_saved,
            "import": self.report.to_dict() if self.report else None,
        }


# --------------------------------------------------------------------------
# 步骤
# --------------------------------------------------------------------------


def step_import(store: SeekdbStore, settings: Settings) -> ImportReport:
    """步骤 1：导入规格、代码与测试资料到 seekdb。"""
    report = import_materials(store, settings.project_dir)
    return report


def step_context(
    store: SeekdbStore,
    settings: Settings,
    task_id: str,
    task_text: str,
    state_client: PowerContextState | None = None,
) -> ContextBundle:
    """步骤 2：检索并组装开发上下文。"""
    state = None
    if state_client is not None:
        try:
            state = state_client.to_state_view(task_id)
        except Exception:  # noqa: BLE001 - PowerContext 不可用时降级为空状态
            state = None
    bundle = build_context(store, settings.project_dir, task_id, task_text, state)
    for record in bundle.queries:
        store.insert_query_log(task_id, record.purpose, record.sql, record.row_count, now())
    store.commit()
    return bundle


def step_apply(
    store: SeekdbStore,
    settings: Settings,
    bundle: ContextBundle,
    client: MiniMaxClient,
    apply_patch: bool = True,
) -> AssistantResult:
    """步骤 3：把上下文交给 MiniMax 完成代码修改。"""
    result = run_assistant(bundle, client, apply_patch=apply_patch)
    if result.diff:
        patch_path = settings.project_dir / "patches" / f"{bundle.task_id}.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(result.diff, encoding="utf-8")
    return result


def step_verify(
    store: SeekdbStore,
    settings: Settings,
    task_id: str,
    phase: str = "after",
    suites: tuple[str, ...] = ("target", "regression"),
) -> list[SuiteResult]:
    """步骤 4：运行目标功能测试与回归测试。"""
    results: list[SuiteResult] = []
    for suite in suites:
        result = run_suite(settings.project_dir, suite, phase=phase)
        results.append(result)
        store.insert_verification(
            {
                "task_id": task_id,
                "phase": phase,
                "suite": suite,
                "command": result.command,
                "exit_code": result.exit_code,
                "passed": result.passed,
                "failed": result.failed,
                "errored": result.errored,
                "summary": result.summary,
                "code_version": result.code_version,
                "created_at": now(),
            }
        )
    store.commit()
    return results


def step_save_state(
    state_client: PowerContextState,
    task_id: str,
    phase: str,
    done: list[str],
    pending: list[str],
    verifications: list[SuiteResult],
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    """步骤 5：把任务状态保存到 PowerContext。"""
    state = TaskState(
        task_id=task_id,
        phase=phase,
        done=done,
        pending=pending,
        verifications=[item.to_dict() for item in verifications],
        artifacts=artifacts or [],
        updated_at=now(),
    )
    response = state_client.save(state)
    return {"state": state.to_dict(), "response": response}


def step_resume(state_client: PowerContextState, task_id: str) -> TaskState | None:
    """步骤 6：模块重启后读取已保存的状态。"""
    return state_client.latest(task_id)


# --------------------------------------------------------------------------
# 记录
# --------------------------------------------------------------------------


def _transport_label(transport: str) -> str:
    """把传输方式写成评审能直接看懂的说明。"""
    return {
        "http": "MiniMax 官方 HTTP API（POST {base}/v1/chat/completions）",
        "cli": "本机 mmx 命令行（已登录账号）",
        "file": "离线重放：读取本次任务中 MiniMax 返回内容的存档 records/minimax_response.json",
        "agent-session": (
            "MiniMax 会话内调用（模型在开发助手的 Agent 会话中直接返回补丁；"
            "上下文由本模块从 seekdb 检索后提供，模型输出原文见本记录第 2 节）"
        ),
    }.get(transport, transport)


def write_minimax_record(
    settings: Settings,
    bundle: ContextBundle,
    result: AssistantResult | None,
) -> Path:
    """写 MiniMax 开发记录。"""
    records = settings.records_dir
    records.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "task_id": bundle.task_id,
        "task": bundle.task_text,
        "context": {
            "specs": [item.to_dict() for item in bundle.specs],
            "code": [item.to_dict() for item in bundle.code],
            "tests": [item.to_dict() for item in bundle.tests],
            "state": bundle.state.to_dict(),
            "queries": [item.to_dict() for item in bundle.queries],
        },
        "minimax": result.to_dict() if result else None,
    }
    json_path = records / "minimax_dev_record.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# MiniMax 开发记录")
    lines.append("")
    lines.append(f"- 任务编号：{bundle.task_id}")
    lines.append(f"- 任务描述：{bundle.task_text}")
    lines.append(f"- 记录时间：{now()}")
    if result:
        lines.append(f"- 模型：{result.model}")
        lines.append(f"- 接入方式：{_transport_label(result.transport)}")
        if result.usage:
            lines.append(f"- token 用量：{json.dumps(result.usage, ensure_ascii=False)}")
        elif result.transport == "agent-session":
            lines.append(
                "- token 用量 / 耗时：会话内调用没有 HTTP 层的计费与耗时统计，故此处为空；"
                "本记录保存的是模型返回的**原始内容**，可与提交的代码差异逐字核对"
            )
        else:
            lines.append(f"- 耗时：{result.latency_ms} ms")
        lines.append(f"- 修改的文件：{', '.join(result.applied_files) or '（无）'}")
    lines.append("")
    lines.append("## 1. 提供给模型的上下文")
    lines.append("")
    lines.append("上下文由 seekdb 检索得到，包含以下来源：")
    lines.append("")
    for item in bundle.specs:
        lines.append(f"- 规格 `{item.spec_id}` {item.title}（{item.locator}）")
    for item in bundle.code:
        lines.append(f"- 代码 `{item.symbol}` @ {item.locator}")
    for item in bundle.tests:
        lines.append(f"- 测试 `{item.name}` [{item.marker}] @ {item.locator}")
    lines.append("")
    lines.append("### 完整提示词")
    lines.append("")
    lines.append("```text")
    lines.append(result.prompt if result else bundle.to_prompt())
    lines.append("```")
    lines.append("")
    lines.append("## 2. 模型的代码修改过程")
    lines.append("")
    if result:
        lines.append("模型返回内容（原文）：")
        lines.append("")
        lines.append("```text")
        lines.append(result.response)
        lines.append("```")
        lines.append("")
        lines.append("从中解析出的 unified diff：")
        lines.append("")
        lines.append("```diff")
        lines.append(result.diff or "（无）")
        lines.append("```")
    else:
        lines.append("（本次运行未调用模型）")
    lines.append("")
    lines.append("## 3. 补丁与提交代码差异的对应关系")
    lines.append("")
    if result and result.applied_files:
        lines.append("补丁应用后修改的文件即提交代码差异涉及的文件：")
        lines.append("")
        for item in result.applied_files:
            lines.append(f"- `{item}`")
    else:
        lines.append("（本次运行未产生代码修改）")
    lines.append("")
    md_path = records / "minimax_dev_record.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def write_db_record(
    settings: Settings,
    store: SeekdbStore,
    bundle: ContextBundle,
    verifications: list[SuiteResult],
) -> Path:
    """写数据库查询记录。"""
    records = settings.records_dir
    records.mkdir(parents=True, exist_ok=True)
    logs = store.fetch_query_log(bundle.task_id)
    payload = {
        "task_id": bundle.task_id,
        "database": "seekdb（嵌入式 pylibseekdb）",
        "queries": [item.to_dict() for item in bundle.queries],
        "query_log": logs,
        "verifications": [item.to_dict() for item in verifications],
    }
    json_path = records / "db_query_record.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 数据库（seekdb）查询记录", ""]
    lines.append(f"- 任务编号：{bundle.task_id}")
    lines.append(f"- 记录时间：{now()}")
    lines.append("- 存储：seekdb 嵌入式实例（pylibseekdb），库名 sddctx")
    lines.append("- 表：spec_entry / code_symbol / test_case / verification_result / query_log")
    lines.append("")
    lines.append("## 1. 用于构造任务上下文的查询")
    lines.append("")
    for index, query in enumerate(bundle.queries, start=1):
        lines.append(f"### 查询 {index}：{query.purpose}（命中 {query.row_count} 行）")
        lines.append("")
        lines.append("```sql")
        lines.append(query.sql.strip())
        lines.append("```")
        lines.append("")
    lines.append("## 2. 查询结果如何进入上下文")
    lines.append("")
    for item in bundle.specs:
        lines.append(
            f"- 规格 `{item.spec_id}`（打分 {item.score}，命中检索词 {', '.join(item.matched_terms) or '任务点名'}）"
        )
    for item in bundle.code:
        lines.append(f"- 代码 `{item.symbol}` @ {item.locator}（{item.reason}）")
    for item in bundle.tests:
        lines.append(f"- 测试 `{item.name}` @ {item.locator}（{item.reason}）")
    lines.append("")
    lines.append("## 3. 验证结果（同一 seekdb 实例落库）")
    lines.append("")
    for item in verifications:
        lines.append(
            f"- [{item.phase}/{item.suite}] 命令 `{item.command}`，退出码 {item.exit_code}，"
            f"通过 {item.passed}、失败 {item.failed}、错误 {item.errored}，版本 {item.code_version}"
        )
    lines.append("")
    lines.append("## 4. query_log 表原始记录")
    lines.append("")
    lines.append("| id | purpose | row_count | created_at |")
    lines.append("| --- | --- | --- | --- |")
    for log in logs:
        purpose = str(log.get("purpose", "")).replace("|", "/")
        lines.append(
            f"| {log.get('id')} | {purpose} | {log.get('row_count')} | {log.get('created_at')} |"
        )
    lines.append("")
    md_path = records / "db_query_record.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def write_state_record(
    settings: Settings,
    task_id: str,
    saved: dict[str, Any] | None,
    resumed: TaskState | None,
    base_url: str,
    scope_id: str,
    resolved_scope_id: str | None = None,
) -> Path:
    """写 PowerContext 状态写入与复用记录。"""
    records = settings.records_dir
    records.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": task_id,
        "powercontext": {
            "base_url": base_url,
            "scope_id": scope_id,
            "resolved_scope_id": resolved_scope_id or scope_id,
            "api": "HTTP API",
        },
        "saved": saved,
        "resumed": resumed.to_dict() if resumed else None,
    }
    json_path = records / "powercontext_state_record.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# PowerContext 状态写入与复用记录", ""]
    lines.append(f"- 任务编号：{task_id}")
    lines.append(f"- 记录时间：{now()}")
    lines.append(f"- 接入方式：HTTP API，Server 地址 {base_url}")
    lines.append(f"- 逻辑作用域：{scope_id}")
    lines.append(f"- 实际作用域：{resolved_scope_id or scope_id}")
    lines.append("")
    lines.append("## 1. 写入（POST /v1/memory/remember）")
    lines.append("")
    if saved:
        state = saved.get("state", {})
        lines.append("保存的内容：")
        lines.append("")
        lines.append("```text")
        lines.append(
            TaskState(
                task_id=state.get("task_id", ""),
                phase=state.get("phase", ""),
                done=state.get("done", []),
                pending=state.get("pending", []),
                verifications=state.get("verifications", []),
                artifacts=state.get("artifacts", []),
                updated_at=state.get("updated_at", ""),
            ).render()
        )
        lines.append("```")
        lines.append("")
        lines.append("服务端返回：")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(saved.get("response", {}), ensure_ascii=False, indent=2))
        lines.append("```")
    else:
        lines.append("（本次运行未写入状态）")
    lines.append("")
    lines.append("## 2. 模块重启后复用（POST /v1/memory/search）")
    lines.append("")
    if resumed:
        lines.append("重启模块后重新读取到的状态：")
        lines.append("")
        lines.append("```text")
        lines.append(resumed.render())
        lines.append("```")
        lines.append("")
        lines.append("该状态被用于后续上下文组装（见 minimax_dev_record.md 的上下文小节）。")
    else:
        lines.append("（未读到状态）")
    lines.append("")
    md_path = records / "powercontext_state_record.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path
