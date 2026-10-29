"""共用的测试夹具。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MINIMAX_DIR = Path(__file__).resolve().parent.parent
if str(MINIMAX_DIR) not in sys.path:
    sys.path.insert(0, str(MINIMAX_DIR))

DEMO_PROJECT = MINIMAX_DIR / "demo_project"


@pytest.fixture()
def project_dir() -> Path:
    """演示工程目录。"""
    return DEMO_PROJECT
