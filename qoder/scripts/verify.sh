#!/usr/bin/env bash
# 复现验收要点：逐项核对"指定技术是否真的在项目功能里发挥作用"。
# 任何一项不通过即以非零码退出。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

VERIFY_LOG="$RECORDS_DIR/verify_run.log"
mkdir -p "$RECORDS_DIR"

log "步骤 1/4：确认服务可用"
ensure_model_server
ensure_powercontext

log "步骤 2/4：确认 seekdb 上的 AI 模型端点已注册"
paperpocket setup-ai

log "步骤 3/4：逐项验收自检"
paperpocket verify --query "$DEMO_QUERY" | tee -a "$VERIFY_LOG"

log "步骤 4/4：复核技术使用记录是否已生成"
for record in db_query_record.md powercontext_memory_record.md demo_output.md; do
  if [ -s "$RECORDS_DIR/$record" ]; then
    echo "  $record 已生成（$(wc -l < "$RECORDS_DIR/$record") 行）"
  else
    echo "  缺少记录文件：$record" >&2
    exit 1
  fi
done

# 记录里必须能看到 PowerContext 的写入与读回（两次运行的证据）。
if ! grep -q "写入（POST /v1/memory/remember）" "$RECORDS_DIR/powercontext_memory_record.md"; then
  echo "  PowerContext 记录缺少写入证据" >&2
  exit 1
fi
if ! grep -q "读回（POST /v1/memory/search）" "$RECORDS_DIR/powercontext_memory_record.md"; then
  echo "  PowerContext 记录缺少读回证据" >&2
  exit 1
fi
echo "  PowerContext 记录包含写入与读回证据"

cat <<EOF

验收自检全部通过。证据文件：
  $RECORDS_DIR/verify_run.log
  $RECORDS_DIR/db_query_record.md
  $RECORDS_DIR/powercontext_memory_record.md
  $RECORDS_DIR/demo_output.md
EOF
