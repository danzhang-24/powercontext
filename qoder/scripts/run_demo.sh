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
# 端到端演示：导入语料 → 第一次检索 → 写入记忆 → 第二次检索 → 生成简报 →
# 记录阅读进度 → 读回记忆。产出全部技术使用记录。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

RUN_LOG="$RECORDS_DIR/demo_run.log"
mkdir -p "$RECORDS_DIR" "$RUNTIME_DIR"

log "步骤 0/8：确认本地模型服务与 PowerContext Server 可用"
ensure_model_server
ensure_powercontext

log "步骤 1/8：确认 seekdb 上的 AI 模型端点已注册"
paperpocket setup-ai

log "步骤 2/8：跑完整演示流程"
paperpocket demo --query "$DEMO_QUERY" | tee -a "$RUN_LOG"

log "步骤 3/8：以独立进程读回 PowerContext 记忆（验证跨进程复用）"
paperpocket recall | tee -a "$RUN_LOG"

log "步骤 4/8：查看数据库与记忆状态"
paperpocket stats | tee -a "$RUN_LOG"

cat <<EOF

演示流程执行完毕。产出：

  records/demo_output.md              演示全过程输出
  records/demo_run.log                命令行记录
  records/db_query_record.md/.json    seekdb 查询记录（真实 SQL 与命中行数）
  records/powercontext_memory_record.md/.json  PowerContext 写入与读回记录
EOF
