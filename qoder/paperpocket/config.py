"""运行期配置。

所有配置项都可以用环境变量覆盖，便于在干净环境里用不同的数据目录重跑；
命令行参数优先于环境变量（见 :func:`load_settings`）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

#: 模块根目录（``qoder/``）。
MODULE_ROOT = Path(__file__).resolve().parent.parent

#: 演示语料目录。
DEFAULT_CORPUS_DIR = Path(os.environ.get("PAPERPOCKET_CORPUS_DIR", MODULE_ROOT / "corpus"))

#: 技术使用记录输出目录。
DEFAULT_RECORDS_DIR = Path(os.environ.get("PAPERPOCKET_RECORDS_DIR", MODULE_ROOT / "records"))

#: 运行期数据目录（PowerContext 作用域绑定、临时文件）。
DEFAULT_RUNTIME_DIR = Path(os.environ.get("PAPERPOCKET_RUNTIME_DIR", MODULE_ROOT / "runtime"))

#: seekdb 默认监听端口。5881 是带全文检索 / 向量索引 / AI 函数的构建。
DEFAULT_DB_PORT = int(os.environ.get("PAPERPOCKET_DB_PORT", "5881"))

#: 向量维度。建表时写入 ``vector(N)``，必须与嵌入实现保持一致。
DEFAULT_EMBED_DIM = int(os.environ.get("PAPERPOCKET_EMBED_DIM", "64"))

#: 本地 OpenAI 兼容模型服务默认地址。
DEFAULT_MODEL_SERVER_URL = os.environ.get(
    "PAPERPOCKET_MODEL_SERVER_URL", "http://127.0.0.1:8300/v1"
)


@dataclass(frozen=True)
class Settings:
    """一次运行使用的全部路径、端点与模型配置。"""

    db_host: str = "127.0.0.1"
    db_port: int = DEFAULT_DB_PORT
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "paperpocket"
    powercontext_url: str = "http://127.0.0.1:8100"
    scope_id: str = "paperpocket:research"
    corpus_dir: Path = DEFAULT_CORPUS_DIR
    records_dir: Path = DEFAULT_RECORDS_DIR
    runtime_dir: Path = DEFAULT_RUNTIME_DIR
    embed_dim: int = DEFAULT_EMBED_DIM
    embed_model: str = "pp_embed"
    complete_model: str = "pp_summarizer"
    model_server_url: str = DEFAULT_MODEL_SERVER_URL
    embed_mode: str = "auto"

    @property
    def scope_binding_path(self) -> Path:
        """PowerContext 作用域绑定文件路径（重启后复用同一个作用域）。"""
        return self.runtime_dir / "scope.json"

    @property
    def model_server_base(self) -> str:
        """模型服务根地址（去掉尾部 ``/v1``）。"""
        base = self.model_server_url.rstrip("/")
        return base[: -len("/v1")] if base.endswith("/v1") else base

    def ensure_dirs(self) -> None:
        """创建运行期需要的目录。"""
        for path in (self.records_dir, self.runtime_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings(**overrides: object) -> Settings:
    """按环境变量装配配置，再应用显式覆盖项。"""
    base = Settings(
        db_host=os.environ.get("PAPERPOCKET_DB_HOST", "127.0.0.1"),
        db_port=int(os.environ.get("PAPERPOCKET_DB_PORT", str(DEFAULT_DB_PORT))),
        db_user=os.environ.get("PAPERPOCKET_DB_USER", "root"),
        db_password=os.environ.get("PAPERPOCKET_DB_PASSWORD", ""),
        db_name=os.environ.get("PAPERPOCKET_DB_NAME", "paperpocket"),
        powercontext_url=os.environ.get(
            "PAPERPOCKET_POWERCONTEXT_URL", "http://127.0.0.1:8100"
        ).rstrip("/"),
        scope_id=os.environ.get("PAPERPOCKET_SCOPE_ID", "paperpocket:research"),
        corpus_dir=Path(os.environ.get("PAPERPOCKET_CORPUS_DIR", str(DEFAULT_CORPUS_DIR))),
        records_dir=Path(os.environ.get("PAPERPOCKET_RECORDS_DIR", str(DEFAULT_RECORDS_DIR))),
        runtime_dir=Path(os.environ.get("PAPERPOCKET_RUNTIME_DIR", str(DEFAULT_RUNTIME_DIR))),
        embed_dim=int(os.environ.get("PAPERPOCKET_EMBED_DIM", str(DEFAULT_EMBED_DIM))),
        embed_model=os.environ.get("PAPERPOCKET_EMBED_MODEL", "pp_embed"),
        complete_model=os.environ.get("PAPERPOCKET_COMPLETE_MODEL", "pp_summarizer"),
        model_server_url=os.environ.get("PAPERPOCKET_MODEL_SERVER_URL", DEFAULT_MODEL_SERVER_URL),
        embed_mode=os.environ.get("PAPERPOCKET_EMBED_MODE", "auto"),
    )
    clean = {key: value for key, value in overrides.items() if value not in (None, "")}
    # 命令行传进来的是字符串，路径字段统一转成 Path。
    for key in ("corpus_dir", "records_dir", "runtime_dir"):
        if key in clean:
            clean[key] = Path(str(clean[key]))
    if clean:
        base = replace(base, **clean)  # type: ignore[arg-type]
    return base
