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
# 端到端演示：导入资料 → 检索上下文 → 交给 MiniMax 改码 → 跑测试 →
# 保存任务状态 → 重启模块后读取复用。产出全部技术使用记录。
#
# 用法：
#   bash scripts/run_demo.sh              # 使用已记录的 MiniMax 响应离线重放
#   SDDCTX_TRANSPORT=http bash scripts/run_demo.sh   # 调用 MiniMax 官方 HTTP 接口
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

TRANSPORT="${SDDCTX_TRANSPORT:-file}"
RECORDED="$RECORDS_DIR/minimax_response.json"
RUN_LOG="$RECORDS_DIR/demo_run.log"

mkdir -p "$RECORDS_DIR" "$MINIMAX_DIR/runtime"

log "步骤 1/6：确认 PowerContext Server 可用"
ensure_server

log "步骤 1.5/6：丢弃旧的作用域绑定，从空状态开始"
sddctx reset-state

log "步骤 2/6：把工程恢复为修改前状态"
sddctx reset

log "步骤 3/6：导入规格 / 代码 / 测试到 seekdb"
sddctx import-materials | tee -a "$RUN_LOG"

log "步骤 4/6：检索开发上下文（改什么 + 哪些原有行为必须保持）"
sddctx context --task "$TASK_TEXT" --out "$RECORDS_DIR/context_T-1.md" | tee -a "$RUN_LOG"

log "步骤 5/6：调用 MiniMax 修改代码，并跑修改前/后两轮测试"
if [ "$TRANSPORT" = "file" ]; then
  sddctx demo --transport file --recorded "$RECORDED" --task "$TASK_TEXT" --reset | tee -a "$RUN_LOG"
else
  sddctx demo --transport "$TRANSPORT" --task "$TASK_TEXT" --reset | tee -a "$RUN_LOG"
fi

log "步骤 6/6：重启模块后读取 PowerContext 中保存的状态"
sddctx resume --task-id T-1 | tee -a "$RUN_LOG"

log "步骤 7/6：保存修改后快照并生成前后差异"
sddctx snapshot --name after | tee -a "$RUN_LOG"

cat <<EOF

演示流程执行完毕。产出：

  records/minimax_dev_record.md          MiniMax 开发记录（上下文 / 模型输出 / 补丁）
  records/db_query_record.md             数据库查询记录（SQL 与命中行数）
  records/powercontext_state_record.md   PowerContext 状态写入与复用记录
  records/context_T-1.md                 本次检索出的开发上下文
  records/demo_run.log                   本次运行的命令行记录
  demo_project/patches/T-1.patch         应用到工程的 unified diff
  demo_project/patches/before-after.patch 修改前后代码差异
  demo_project/snapshots/before|after/     修改前后代码快照
  demo_project/logs/*.log                修改前后四组测试的运行日志
EOF
