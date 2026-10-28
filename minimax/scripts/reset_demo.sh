#!/usr/bin/env bash
# 把演示工程恢复到"修改前"状态：源码、测试与规格全部回到 snapshots/before。
# 用法：bash scripts/reset_demo.sh [--wipe-runtime]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

log "恢复演示工程到修改前状态"
sddctx reset

if [ "${1:-}" = "--wipe-runtime" ]; then
  log "清空运行期数据（seekdb 索引与 PowerContext 本地库）"
  rm -rf "$MINIMAX_DIR/runtime"
  mkdir -p "$MINIMAX_DIR/runtime"
fi

echo "已重置。目标功能测试（target）此时应当失败，回归测试（regression）应当通过。"
