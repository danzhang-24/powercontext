"""运行期配置。

所有路径都可以用环境变量覆盖，便于在干净环境里用不同的数据目录重跑。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: minimax/ 目录（模块根）。
MODULE_ROOT = Path(__file__).resolve().parent.parent

#: 演示业务工程目录。
DEFAULT_PROJECT_DIR = MODULE_ROOT / "demo_project"

#: 运行期数据目录（seekdb 数据、临时工作区）。
DEFAULT_WORK_DIR = Path(os.environ.get("SDDCTX_HOME", MODULE_ROOT / "runtime"))

#: 技术使用记录输出目录。默认落在模块目录内，便于随代码一起提交评审。
DEFAULT_RECORDS_DIR = Path(os.environ.get("SDDCTX_RECORDS_DIR", MODULE_ROOT / "records"))

#: PowerContext Server 地址。
DEFAULT_POWERCONTEXT_URL = os.environ.get("POWERCONTEXT_SERVER_URL", "http://127.0.0.1:8000")

#: 上下文作用域（PowerContext scope_id）。
DEFAULT_SCOPE_ID = os.environ.get("SDDCTX_SCOPE_ID", "sddctx:order-discount")

#: MiniMax 接口地址。global 对应 api.minimax.io，cn 对应 api.minimaxi.com。
_MINIMAX_BASES = {
    "global": "https://api.minimax.io",
    "cn": "https://api.minimaxi.com",
}


def minimax_base_url() -> str:
    """返回 MiniMax 接口根地址。"""
    explicit = os.environ.get("MINIMAX_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    region = os.environ.get("MINIMAX_REGION", "global").strip().lower()
    return _MINIMAX_BASES.get(region, _MINIMAX_BASES["global"])


def minimax_model() -> str:
    """返回默认使用的 MiniMax 文本模型。"""
    return os.environ.get("MINIMAX_MODEL", "MiniMax-M3")


def minimax_api_key() -> str | None:
    """返回 MiniMax API Key。

    优先使用 ``MINIMAX_API_KEY`` 环境变量；否则回落到 mmx CLI 登录后的
    ``~/.mmx/credentials.json`` / ``~/.mmx/config.json``。
    """
    key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("MINIMAX_APIKEY")
    if key:
        return key.strip()
    return _read_mmux_key()


def _read_mmux_key() -> str | None:
    """从 mmx CLI 的本地凭据文件读取 API Key。"""
    import json

    config_dir = Path(os.environ.get("MMX_CONFIG_DIR", Path.home() / ".mmx"))
    for name in ("credentials.json", "config.json"):
        path = config_dir / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for candidate in _find_key(data):
            if candidate:
                return candidate
    return None


def _find_key(node):
    """在嵌套结构里查找看起来像 API Key 的字符串。"""
    if isinstance(node, str):
        return [node] if node.startswith("sk-") else []
    if isinstance(node, dict):
        found = []
        for value in node.values():
            found.extend(_find_key(value))
        return found
    if isinstance(node, list):
        found = []
        for value in node:
            found.extend(_find_key(value))
        return found
    return []


@dataclass(frozen=True)
class Settings:
    """一次运行使用的全部路径与端点配置。"""

    project_dir: Path = DEFAULT_PROJECT_DIR
    work_dir: Path = DEFAULT_WORK_DIR
    powercontext_url: str = DEFAULT_POWERCONTEXT_URL
    scope_id: str = DEFAULT_SCOPE_ID
    records_dir: Path = DEFAULT_RECORDS_DIR

    @property
    def db_dir(self) -> Path:
        """嵌入式 seekdb 数据目录。"""
        return self.work_dir / "seekdb"

    @property
    def workspace_dir(self) -> Path:
        """临时工作区（补丁、上下文快照）。"""
        return self.work_dir / "workspace"

    def ensure_dirs(self) -> None:
        """创建运行期需要的目录。"""
        for path in (self.work_dir, self.db_dir, self.records_dir, self.workspace_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings(
    project_dir: str | os.PathLike[str] | None = None,
    work_dir: str | os.PathLike[str] | None = None,
    powercontext_url: str | None = None,
    scope_id: str | None = None,
    records_dir: str | os.PathLike[str] | None = None,
) -> Settings:
    """组装配置，命令行参数优先于环境变量。"""
    return Settings(
        project_dir=Path(project_dir).resolve() if project_dir else DEFAULT_PROJECT_DIR,
        work_dir=Path(work_dir).resolve() if work_dir else DEFAULT_WORK_DIR,
        powercontext_url=(powercontext_url or DEFAULT_POWERCONTEXT_URL).rstrip("/"),
        scope_id=scope_id or DEFAULT_SCOPE_ID,
        records_dir=Path(records_dir).resolve() if records_dir else DEFAULT_RECORDS_DIR,
    )
