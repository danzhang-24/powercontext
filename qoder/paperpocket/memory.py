"""PowerContext 记忆读写。

接入方式：PowerContext HTTP API（``/v1/scopes``、``/v1/memory/remember``、
``/v1/memory/search``），版本见 ``docs/run-guide.md``。

记忆内容使用固定的可解析文本格式（首行 ``paperpocket-memory v1``），
这样下次检索时可以把记忆重新解析成结构化对象，真正参与检索打分：

- ``type: profile``——研究方向与常用标签；
- ``type: history``——历史检索词与当时命中的资料键；
- ``type: progress``——阅读进度（哪篇读过、读到哪一段）。

作用域绑定写入本地文件（``runtime/scope.json``），模块重启后仍然指向同一个
作用域；删除该文件即可从空记忆开始。
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

#: 记忆条目的固定首行。
MEMORY_HEADER = "paperpocket-memory v1"

#: PowerContext ``/v1/memory/search`` 允许的最大 limit（服务端返回 422 时超限）。
MAX_SEARCH_LIMIT = 50


class PowerContextError(RuntimeError):
    """PowerContext 调用失败。"""


def _now() -> str:
    """返回当前 UTC 时间戳（秒级 ISO 格式）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class MemoryProfile:
    """研究方向画像。"""

    direction: str = ""
    tags: list[str] = field(default_factory=list)
    updated_at: str = ""

    @property
    def keywords(self) -> list[str]:
        """把研究方向拆成关键词（空格分隔）。"""
        return [part for part in self.direction.replace("，", " ").split() if part]


@dataclass
class MemoryHistoryItem:
    """一条历史检索。"""

    query: str = ""
    top_keys: list[str] = field(default_factory=list)
    at: str = ""


@dataclass
class MemoryProgressItem:
    """一条阅读进度。"""

    doc_key: str = ""
    title: str = ""
    status: str = "read"
    chunk_key: str = ""
    at: str = ""


@dataclass
class MemorySnapshot:
    """一次读回的全部记忆。"""

    scope_id: str = ""
    profile: MemoryProfile = field(default_factory=MemoryProfile)
    history: list[MemoryHistoryItem] = field(default_factory=list)
    progress: list[MemoryProgressItem] = field(default_factory=list)
    raw_entries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def read_doc_keys(self) -> set[str]:
        """已经读过（或在读）的资料键集合。"""
        return {item.doc_key for item in self.progress if item.doc_key}

    @property
    def is_empty(self) -> bool:
        """是否没有任何可用记忆。"""
        return not (self.profile.direction or self.profile.tags or self.history or self.progress)


def _render(entry_type: str, fields: dict[str, str]) -> str:
    """把一条记忆渲染成固定格式的文本。"""
    lines = [MEMORY_HEADER, f"type: {entry_type}"]
    lines.extend(f"{key}: {value}" for key, value in fields.items() if value != "")
    return "\n".join(lines)


def _parse(text: str) -> dict[str, str]:
    """解析一条记忆文本，返回键值字典。"""
    if not text.lstrip().startswith(MEMORY_HEADER):
        return {}
    fields: dict[str, str] = {}
    for raw in text.splitlines()[1:]:
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    return fields


class MemoryStore:
    """PowerContext 记忆客户端。"""

    def __init__(
        self,
        base_url: str,
        scope_id: str,
        binding_path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.scope_id = scope_id
        self.timeout = timeout
        self.binding_path = Path(binding_path) if binding_path else None
        self._resolved_scope: str | None = None

    # -- HTTP 基础 --------------------------------------------------------
    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        """发起一次 HTTP 请求并解析 JSON 响应。"""
        url = f"{self.base_url}{path}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise PowerContextError(
                f"PowerContext {method} {path} 失败（HTTP {exc.code}）：{detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PowerContextError(
                f"无法连接 PowerContext Server（{self.base_url}）：{exc}。"
                "请先执行 `powercontext server run --env-file scripts/powercontext.env` 启动服务。"
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

    def ensure_scope(self) -> str:
        """确保作用域存在，返回可用的 scope_id。"""
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
                    "title": f"PaperPocket {self.scope_id}",
                    "summary": "PaperPocket 研究记忆：方向偏好、检索历史与阅读进度",
                    "idempotency_key": f"paperpocket:{self.scope_id}:{uuid4().hex[:8]}",
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
    def remember(self, entry_type: str, fields: dict[str, str], reason: str) -> dict[str, Any]:
        """写入一条记忆，返回服务端响应。"""
        scope_id = self.ensure_scope()
        text = _render(entry_type, fields)
        response = self._request(
            "POST",
            "/v1/memory/remember",
            {
                "scope_id": scope_id,
                "kind": f"paperpocket.{entry_type}",
                "text": text,
                "reason": reason,
            },
        )
        response = dict(response) if isinstance(response, dict) else {}
        response["text"] = text
        response["entry_type"] = entry_type
        return response

    def remember_profile(self, direction: str, tags: list[str]) -> dict[str, Any]:
        """记住研究方向与常用标签。"""
        return self.remember(
            "profile",
            {
                "direction": direction,
                "tags": ",".join(tags),
                "updated_at": _now(),
            },
            reason=f"记住研究方向：{direction}",
        )

    def remember_query(self, query: str, top_keys: list[str]) -> dict[str, Any]:
        """记住一次检索及其命中。"""
        return self.remember(
            "history",
            {
                "query": query,
                "top_keys": ",".join(top_keys),
                "at": _now(),
            },
            reason=f"记住检索历史：{query}",
        )

    def remember_progress(self, doc_key: str, title: str, status: str = "read",
                          chunk_key: str = "") -> dict[str, Any]:
        """记住阅读进度。"""
        return self.remember(
            "progress",
            {
                "doc_key": doc_key,
                "title": title,
                "status": status,
                "chunk_key": chunk_key,
                "at": _now(),
            },
            reason=f"记住阅读进度：{title}",
        )

    def search_memories(self, query: str, limit: int = MAX_SEARCH_LIMIT) -> list[dict[str, Any]]:
        """在作用域内检索记忆条目。"""
        scope_id = self.ensure_scope()
        response = self._request(
            "POST",
            "/v1/memory/search",
            {
                "scope_id": scope_id,
                "query": query,
                "limit": max(1, min(int(limit), MAX_SEARCH_LIMIT)),
            },
        )
        hits = response.get("hits") or [] if isinstance(response, dict) else []
        return [hit for hit in hits if isinstance(hit, dict)]

    def load(self, limit: int = MAX_SEARCH_LIMIT) -> MemorySnapshot:
        """读回全部记忆并解析成结构化快照。"""
        scope_id = self.ensure_scope()
        hits = self.search_memories("paperpocket", limit=limit)
        snapshot = MemorySnapshot(scope_id=scope_id)
        for hit in hits:
            text = str(hit.get("text") or "")
            fields = _parse(text)
            if not fields:
                continue
            snapshot.raw_entries.append({"text": text, "score": hit.get("score")})
            entry_type = fields.get("type", "")
            if entry_type == "profile":
                snapshot.profile = MemoryProfile(
                    direction=fields.get("direction", ""),
                    tags=[tag for tag in fields.get("tags", "").split(",") if tag],
                    updated_at=fields.get("updated_at", ""),
                )
            elif entry_type == "history":
                snapshot.history.append(
                    MemoryHistoryItem(
                        query=fields.get("query", ""),
                        top_keys=[key for key in fields.get("top_keys", "").split(",") if key],
                        at=fields.get("at", ""),
                    )
                )
            elif entry_type == "progress":
                snapshot.progress.append(
                    MemoryProgressItem(
                        doc_key=fields.get("doc_key", ""),
                        title=fields.get("title", ""),
                        status=fields.get("status", "read"),
                        chunk_key=fields.get("chunk_key", ""),
                        at=fields.get("at", ""),
                    )
                )
        snapshot.history.sort(key=lambda item: item.at)
        return snapshot
