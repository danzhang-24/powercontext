"""MiniMax 客户端。

支持两种接入方式（运行说明里会注明本次实际使用的方式与版本）：

- ``http``：直接调用 MiniMax OpenAI 兼容接口 ``POST {base}/v1/chat/completions``。
- ``cli``：调用本机安装的 ``mmx`` 命令行（``mmx text chat``）。

另外提供 ``file`` 方式：读取一次真实调用留下的响应文件，用于在离线环境
重放同一次开发过程（记录里会写明该响应的来源）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import minimax_api_key, minimax_base_url, minimax_model

DEFAULT_SYSTEM_PROMPT = (
    "你是一名资深 Python 工程师。严格按照给定的规格条目修改代码，"
    "只输出一个 unified diff 格式的补丁，不要输出解释性文字。"
)


class MiniMaxError(RuntimeError):
    """MiniMax 调用失败。"""


@dataclass
class ChatResult:
    """一次模型调用的结果。"""

    content: str
    model: str
    transport: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "transport": self.transport,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "content": self.content,
        }


class MiniMaxClient:
    """MiniMax 文本模型客户端。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        transport: str = "http",
        timeout: float = 180.0,
        response_file: str | os.PathLike[str] | None = None,
    ):
        self.api_key = api_key if api_key is not None else minimax_api_key()
        self.base_url = (base_url or minimax_base_url()).rstrip("/")
        self.model = model or minimax_model()
        self.transport = transport
        self.timeout = timeout
        self.response_file = response_file

    # -- 对外接口 ---------------------------------------------------------
    def chat(
        self,
        prompt: str,
        system: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> ChatResult:
        """发起一次对话补全。"""
        if self.transport == "cli":
            return self._chat_cli(prompt, system, max_tokens, temperature)
        if self.transport == "file":
            if not self.response_file:
                raise MiniMaxError("file 方式需要指定 response_file")
            return self.load_recorded(self.response_file)
        return self._chat_http(prompt, system, max_tokens, temperature)

    def load_recorded(self, path: str | os.PathLike[str]) -> ChatResult:
        """读取一次真实调用保存下来的响应。"""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return ChatResult(
            content=payload["content"],
            model=payload.get("model", self.model),
            transport=payload.get("transport", "http"),
            usage=payload.get("usage", {}),
            latency_ms=int(payload.get("latency_ms", 0)),
            raw=payload.get("raw"),
        )

    # -- HTTP 方式 --------------------------------------------------------
    def _chat_http(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> ChatResult:
        if not self.api_key:
            raise MiniMaxError(
                "缺少 MiniMax API Key：请设置 MINIMAX_API_KEY 环境变量，"
                "或执行 `mmx auth login --api-key sk-xxxxx` 后重试"
            )
        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.time()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover - 网络异常
            detail = exc.read().decode("utf-8", "replace")
            raise MiniMaxError(f"MiniMax HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - 网络异常
            raise MiniMaxError(f"MiniMax 请求失败: {exc}") from exc
        latency_ms = int((time.time() - started) * 1000)

        payload = json.loads(raw)
        choices = payload.get("choices") or []
        if not choices:
            raise MiniMaxError(f"MiniMax 返回内容为空: {raw[:400]}")
        content = (choices[0].get("message") or {}).get("content") or ""
        return ChatResult(
            content=content,
            model=payload.get("model", self.model),
            transport="http",
            usage=payload.get("usage") or {},
            latency_ms=latency_ms,
            raw=payload,
        )

    # -- mmx CLI 方式 -----------------------------------------------------
    def _chat_cli(
        self,
        prompt: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> ChatResult:
        binary = shutil.which("mmx")
        if not binary:
            raise MiniMaxError("未找到 mmx 命令，请先 `npm install -g mmx-cli`")
        command = [
            binary,
            "text",
            "chat",
            "--message",
            f"system:{system}",
            "--message",
            f"user:{prompt}",
            "--model",
            self.model,
            "--max-tokens",
            str(max_tokens),
            "--temperature",
            str(temperature),
            "--output",
            "json",
            "--quiet",
            "--non-interactive",
        ]
        started = time.time()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout + 60)
        latency_ms = int((time.time() - started) * 1000)
        if completed.returncode != 0:
            raise MiniMaxError(
                f"mmx 调用失败（退出码 {completed.returncode}）：{completed.stderr.strip()[:400]}"
            )
        try:
            payload = json.loads(completed.stdout)
        except ValueError as exc:
            raise MiniMaxError(f"mmx 输出不是 JSON: {completed.stdout[:200]}") from exc
        content = payload.get("content") or payload.get("reply") or ""
        return ChatResult(
            content=content,
            model=payload.get("model", self.model),
            transport="cli",
            usage=payload.get("usage") or {},
            latency_ms=latency_ms,
            raw=payload,
        )
