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
"""运行目标功能测试与回归测试，并把结果写回 seekdb。

每次运行都记录：命令、退出码、统计数字、对应代码版本。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed)")

#: 需要纳入版本号的文件后缀。
_VERSION_SUFFIXES = (".py", ".md", ".ini")


@dataclass
class SuiteResult:
    """一次测试套件的执行结果。"""

    phase: str
    suite: str
    command: str
    exit_code: int
    passed: int
    failed: int
    errored: int
    summary: str
    code_version: str
    stdout: str = ""
    stderr: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "suite": self.suite,
            "command": self.command,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "failed": self.failed,
            "errored": self.errored,
            "summary": self.summary,
            "code_version": self.code_version,
        }


def project_version(project_dir: Path) -> str:
    """计算工程版本标识：git commit + 源码内容摘要。"""
    project_dir = Path(project_dir).resolve()
    digest = hashlib.sha256()
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in _VERSION_SUFFIXES:
            continue
        if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        digest.update(path.relative_to(project_dir).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    head = _git_head(project_dir)
    return f"{head}+content:{digest.hexdigest()[:12]}"


def _git_head(project_dir: Path) -> str:
    """取 git commit（取不到时返回 nogit）。"""
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_dir), "rev-parse", "--short=12", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return "nogit"
    if completed.returncode != 0:
        return "nogit"
    return completed.stdout.strip() or "nogit"


def run_suite(project_dir: Path, suite: str, phase: str = "after", python: str | None = None) -> SuiteResult:
    """运行一个测试套件。

    Args:
        project_dir: 演示工程目录。
        suite: ``target`` / ``regression`` / ``all``。
        phase: ``before`` / ``after``，用于区分修改前后的运行。
    """
    project_dir = Path(project_dir).resolve()
    interpreter = python or sys.executable
    command = [interpreter, "-m", "pytest", "-p", "no:cacheprovider", "-q"]
    if suite != "all":
        command += ["-m", suite]
    command_text = " ".join(command)

    completed = subprocess.run(
        command,
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    passed, failed, errored = _parse_counts(stdout + stderr)
    summary = _summary_line(stdout) or _summary_line(stderr) or f"exit={completed.returncode}"
    return SuiteResult(
        phase=phase,
        suite=suite,
        command=command_text,
        exit_code=completed.returncode,
        passed=passed,
        failed=failed,
        errored=errored,
        summary=summary,
        code_version=project_version(project_dir),
        stdout=stdout,
        stderr=stderr,
    )


def _parse_counts(text: str) -> tuple[int, int, int]:
    """从 pytest 输出里解析 通过/失败/错误 数量。"""
    passed = failed = errored = 0
    for count, label in _COUNT_RE.findall(text):
        value = int(count)
        if label == "passed":
            passed += value
        elif label == "failed":
            failed += value
        elif label in {"error", "errors"}:
            errored += value
    return passed, failed, errored


def _summary_line(text: str) -> str:
    """取 pytest 输出里最后一行统计。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if re.search(r"\d+\s+(passed|failed|error)", line):
            return line
    return ""
