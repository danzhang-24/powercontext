#!/usr/bin/env bash
# 跑 PaperPocket 的测试。任一用例失败即以非零码退出。
#
# 用法（在 qoder/ 目录下）：
#   bash tests/run_tests.sh
#
# 说明：集成用例需要 seekdb（127.0.0.1:5881）与 PowerContext（127.0.0.1:8100）
# 在运行；没有启动时这些用例会跳过，离线单元用例仍然执行。
set -euo pipefail

QODER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$QODER_DIR"

if [ -x "$QODER_DIR/.venv/bin/python" ]; then
  PYTHON="$QODER_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

echo "=== 解释器：$($PYTHON -V 2>&1) ==="
echo "=== pytest：tests/ ==="
"$PYTHON" -m pytest tests/ -v
echo "=== 全部测试通过 ==="
