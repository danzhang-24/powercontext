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
