"""本地 OpenAI 兼容模型服务（演示用，无外网也能跑通）。

seekdb 的 ``AI_EMBED`` / ``AI_COMPLETE`` 需要一个 OpenAI 兼容的模型端点。本模块
提供一个零依赖的本地实现：

- ``POST /v1/embeddings``——把文本转成确定性的哈希向量（与
  :mod:`paperpocket.embedding` 使用同一套词元与分桶规则）；
- ``POST /v1/chat/completions``——把提示词里的资料片段压缩成要点式摘要
  （与 :func:`paperpocket.brief.extractive_summary` 同一套算法）。

把它注册到 seekdb 上之后，``AI_EMBED`` / ``AI_COMPLETE`` 走的是真实的数据库
调用链路。换成任何真实的 OpenAI 兼容服务也只需要改一个 URL。

用法::

    python -m paperpocket.model_server --port 8300
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .brief import extractive_summary, parse_passages
from .embedding import hash_embedding

#: 请求日志（线程安全追加）。
_LOG_LOCK = threading.Lock()


def _log_requests(path: str | None) -> None:
    """把收到的请求写入日志文件，便于核对真实调用。"""
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": _now(), **_LAST_REQUEST}, ensure_ascii=False) + "\n")


def _now() -> str:
    """返回当前 UTC 时间戳。"""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


#: 最近一次请求的摘要（写入日志用）。
_LAST_REQUEST: dict[str, Any] = {}


class ModelHandler(BaseHTTPRequestHandler):
    """处理 OpenAI 兼容请求。"""

    protocol_version = "HTTP/1.1"
    server_version = "PaperPocketModelServer/1.0"

    # -- 工具 -------------------------------------------------------------
    def _send(self, status: int, payload: dict[str, Any]) -> None:
        """发送 JSON 响应。"""
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: Any) -> None:
        """屏蔽默认访问日志（避免污染终端输出）。"""
        return

    # -- 路由 -------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        """处理 GET 请求。"""
        if self.path.rstrip("/").endswith("/models"):
            self._send(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": "paperpocket-local", "object": "model", "owned_by": "paperpocket"}
                    ],
                },
            )
            return
        self._send(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        """处理 POST 请求。"""
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            body = {}
        global _LAST_REQUEST
        _LAST_REQUEST = {"path": self.path, "body": body}

        path = self.path.rstrip("/")
        if path.endswith("/embeddings"):
            self._handle_embeddings(body)
            return
        if path.endswith("/chat/completions"):
            self._handle_chat(body)
            return
        self._send(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    # -- 业务 -------------------------------------------------------------
    def _handle_embeddings(self, body: dict[str, Any]) -> None:
        """返回确定性哈希向量。"""
        dim = int(self.server.embed_dim)  # type: ignore[attr-defined]
        raw_input = body.get("input", "")
        if isinstance(raw_input, list):
            texts = [str(item) for item in raw_input]
        else:
            texts = [str(raw_input)]
        data = []
        for index, text in enumerate(texts):
            vector = hash_embedding(text, dim)
            data.append({"object": "embedding", "index": index, "embedding": vector})
        _log_requests(self.server.request_log)  # type: ignore[attr-defined]
        self._send(200, {"object": "list", "data": data, "model": body.get("model", "paperpocket-local")})

    def _handle_chat(self, body: dict[str, Any]) -> None:
        """按提示词生成要点式摘要。"""
        messages = body.get("messages") or []
        prompt = ""
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "user":
                prompt = str(message.get("content") or "")
        passages = parse_passages(prompt)
        query = ""
        if "【检索词】" in prompt:
            query = prompt.split("【检索词】", 1)[1].split("【资料片段】", 1)[0].strip()
        summary = extractive_summary(passages, query)
        _log_requests(self.server.request_log)  # type: ignore[attr-defined]
        self._send(
            200,
            {
                "id": "paperpocket-local",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": summary},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": len(prompt), "completion_tokens": len(summary)},
            },
        )


class ModelServer(ThreadingHTTPServer):
    """带嵌入维度与请求日志配置的模型服务。"""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], embed_dim: int, request_log: str | None) -> None:
        super().__init__(address, ModelHandler)
        self.embed_dim = embed_dim
        self.request_log = request_log


def serve(port: int = 8300, host: str = "127.0.0.1", embed_dim: int = 64,
          request_log: str | None = None) -> None:
    """启动模型服务（阻塞）。"""
    server = ModelServer((host, port), embed_dim, request_log)
    print(f"PaperPocket 本地模型服务已启动：http://{host}:{port}/v1（嵌入维度 {embed_dim}）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - 手动中断
        pass
    finally:
        server.server_close()


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="PaperPocket 本地 OpenAI 兼容模型服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8300, help="监听端口（默认 8300）")
    parser.add_argument("--embed-dim", type=int, default=64, help="嵌入维度（默认 64）")
    parser.add_argument("--request-log", default=None, help="请求日志文件路径")
    args = parser.parse_args()
    serve(
        port=args.port,
        host=args.host,
        embed_dim=args.embed_dim,
        request_log=args.request_log,
    )


if __name__ == "__main__":  # pragma: no cover - 脚本入口
    main()
