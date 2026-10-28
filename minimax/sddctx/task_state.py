"""PowerContext 任务状态读写。

接入方式：PowerContext HTTP API（``/v1/scopes``、``/v1/memory/remember``、
``/v1/memory/search``），版本见运行说明。

状态以一条 Memory 条目保存，文本采用固定的行式格式，便于再次读取后解析复用。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .context import StateView, VerificationView

#: 状态条目的固定首行，便于识别与过滤。
STATE_HEADER = "sddctx-state v1"


class PowerContextError(RuntimeError):
    """PowerContext 调用失败。"""


@dataclass
class TaskState:
    """一次任务的状态快照。"""

    task_id: str
    phase: str
    done: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    verifications: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "phase": self.phase,
            "done": self.done,
            "pending": self.pending,
            "verifications": self.verifications,
            "artifacts": self.artifacts,
            "updated_at": self.updated_at,
        }

    def render(self) -> str:
        """渲染成保存到 PowerContext 的文本。"""
        lines = [
            STATE_HEADER,
            f"task: {self.task_id}",
            f"phase: {self.phase}",
            f"updated_at: {self.updated_at or datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            "done:",
        ]
        lines.extend(f"- {item}" for item in self.done)
        lines.append("pending:")
        lines.extend(f"- {item}" for item in self.pending)
        lines.append("artifacts:")
        lines.extend(f"- {item}" for item in self.artifacts)
        lines.append("verifications:")
        for item in self.verifications:
            lines.append(
                "- phase={phase} suite={suite} exit_code={exit_code} passed={passed} "
                "failed={failed} errored={errored} code_version={code_version} summary={summary}".format(
                    **item
                )
            )
        return "\n".join(lines)

    @staticmethod
    def parse(text: str) -> "TaskState | None":
        """解析状态文本；不是本模块的条目时返回 None。"""
        if not text or not text.lstrip().startswith(STATE_HEADER):
            return None
        state = TaskState(task_id="", phase="")
        section: str | None = None
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            if line.startswith("- "):
                item = line[2:].strip()
                if section == "done":
                    state.done.append(item)
                elif section == "pending":
                    state.pending.append(item)
                elif section == "artifacts":
                    state.artifacts.append(item)
                elif section == "verifications":
                    state.verifications.append(_parse_verification(item))
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key in {"done", "pending", "artifacts", "verifications"}:
                section = key
                continue
            section = None
            if key == "task":
                state.task_id = value
            elif key == "phase":
                state.phase = value
            elif key == "updated_at":
                state.updated_at = value
        return state


def _parse_verification(item: str) -> dict[str, Any]:
    """解析一行验证结果。``summary`` 取该字段之后的全部剩余文本。"""
    result: dict[str, Any] = {
        "phase": "",
        "suite": "",
        "exit_code": 0,
        "passed": 0,
        "failed": 0,
        "errored": 0,
        "summary": "",
        "code_version": "",
    }
    text = item
    if " summary=" in text:
        text, _, summary = text.partition(" summary=")
        result["summary"] = summary.strip()
    for token in text.split(" "):
        key, _, value = token.partition("=")
        if key in {"phase", "suite", "code_version"}:
            result[key] = value
        elif key in {"exit_code", "passed", "failed", "errored"}:
            try:
                result[key] = int(value)
            except ValueError:
                result[key] = 0
    return result


class PowerContextState:
    """PowerContext 任务状态客户端。

    作用域绑定会写入本地文件（``scope.json``）。模块重启后读取同一个绑定，
    就能继续复用上一次保存的任务状态；删除该文件则下次从空作用域开始。
    """

    def __init__(
        self,
        base_url: str,
        scope_id: str,
        timeout: float = 30.0,
        binding_path: str | Path | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.scope_id = scope_id
        self.timeout = timeout
        self.binding_path = Path(binding_path) if binding_path else None
        self._resolved_scope: str | None = None

    # -- HTTP 基础 --------------------------------------------------------
    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise PowerContextError(f"PowerContext {method} {path} 失败（HTTP {exc.code}）：{detail}") from exc
        except urllib.error.URLError as exc:
            raise PowerContextError(
                f"无法连接 PowerContext Server（{self.base_url}）：{exc}。"
                "请先执行 `powercontext server run --env-file <env>` 启动服务。"
            ) from exc
        if not body.strip():
            return {}
        return json.loads(body)

    # -- 能力 -------------------------------------------------------------
    def available(self) -> bool:
        """PowerContext Server 是否可用。"""
        try:
            self._request("GET", "/health/live")
            return True
        except PowerContextError:
            return False

    def capabilities(self) -> dict[str, Any]:
        """读取服务端能力，便于在记录里说明实际接入方式。"""
        return self._request("GET", "/v1/capabilities")

    def ensure_scope(self) -> str:
        """确保作用域存在，返回可用的 scope_id。

        优先复用本地记录的绑定（模块重启后仍指向同一个作用域），
        绑定不存在时新建一个作用域并把绑定写回本地。
        """
        if self._resolved_scope:
            return self._resolved_scope
        binding = self._load_binding()
        if binding:
            self._resolved_scope = binding["scope_id"]
            return self._resolved_scope
        try:
            descriptor = self._request(
                "POST",
                "/v1/scopes",
                {
                    "title": f"sddctx {self.scope_id}",
                    "summary": "SDD 上下文模块保存的任务状态与验证结果",
                    "idempotency_key": f"sddctx:{self.scope_id}:{uuid4().hex[:8]}",
                },
            )
            self._resolved_scope = descriptor.get("scope_id") or self.scope_id
        except PowerContextError:
            self._resolved_scope = self.scope_id
        self._save_binding(self._resolved_scope)
        return self._resolved_scope

    def forget_scope(self) -> None:
        """丢弃本地作用域绑定：下次访问会新建一个空作用域。"""
        if self.binding_path and self.binding_path.is_file():
            self.binding_path.unlink()
        self._resolved_scope = None

    def _load_binding(self) -> dict[str, Any] | None:
        """读取本地作用域绑定。"""
        if not self.binding_path or not self.binding_path.is_file():
            return None
        try:
            data = json.loads(self.binding_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if data.get("base_url") != self.base_url or not data.get("scope_id"):
            return None
        return data

    def _save_binding(self, scope_id: str) -> None:
        """把作用域绑定写入本地文件。"""
        if not self.binding_path:
            return
        self.binding_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "base_url": self.base_url,
            "scope_id": scope_id,
            "logical_scope": self.scope_id,
        }
        self.binding_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- 读写 -------------------------------------------------------------
    def save(self, state: TaskState) -> dict[str, Any]:
        """把任务状态写入 PowerContext。"""
        scope_id = self.ensure_scope()
        response = self._request(
            "POST",
            "/v1/memory/remember",
            {
                "scope_id": scope_id,
                "kind": "sddctx.task_state",
                "text": state.render(),
                "reason": f"保存任务 {state.task_id} 的进度与验证结果（阶段 {state.phase}）",
            },
        )
        return response

    def load(self, task_id: str, limit: int = 20) -> list[TaskState]:
        """按任务号读取保存过的状态。"""
        scope_id = self.ensure_scope()
        response = self._request(
            "POST",
            "/v1/memory/search",
            {
                "scope_id": scope_id,
                "query": f"sddctx-state task={task_id}",
                "limit": limit,
            },
        )
        states: list[TaskState] = []
        for hit in response.get("hits") or []:
            parsed = TaskState.parse(hit.get("text") or "")
            if parsed and parsed.task_id == task_id:
                states.append(parsed)
        states.sort(key=lambda item: item.updated_at)
        return states

    def latest(self, task_id: str) -> TaskState | None:
        """取最近一次保存的状态。"""
        states = self.load(task_id)
        return states[-1] if states else None

    def to_state_view(self, task_id: str) -> StateView:
        """把 PowerContext 中的状态转成上下文里的状态视图。"""
        states = self.load(task_id)
        view = StateView(scope_id=self.scope_id, source="powercontext")
        for state in states:
            view.entries.append(state.to_dict())
        if states:
            latest = states[-1]
            view.done = list(latest.done)
            view.pending = list(latest.pending)
            view.verifications = [
                VerificationView(
                    phase=item.get("phase", ""),
                    suite=item.get("suite", ""),
                    command="",
                    exit_code=int(item.get("exit_code", 0)),
                    passed=int(item.get("passed", 0)),
                    failed=int(item.get("failed", 0)),
                    errored=int(item.get("errored", 0)),
                    summary=item.get("summary", ""),
                    code_version=item.get("code_version", ""),
                )
                for item in latest.verifications
            ]
        return view
