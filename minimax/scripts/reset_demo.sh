#!/usr/bin/env bash
#!/bin/sh
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
