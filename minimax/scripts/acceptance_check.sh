#!/usr/bin/env bash
# 一次性自检赛题六项必做项，并留下可核对的运行日志。
#
#   bash scripts/acceptance_check.sh
#
# 赛题的六项必做项（任一不过整题 0 分），这里逐项给出复现命令与实测结果，
# 全部日志写入 records/acceptance_run.log。
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

LOG="$RECORDS_DIR/acceptance_run.log"
mkdir -p "$RECORDS_DIR"
: > "$LOG"

PASS=0
FAIL=0

run_step() {
  # run_step "<标题>" <命令...>
  local title="$1"; shift
  {
    echo
    echo "──────────────────────────────────────────────────────────────"
    echo "▶ $title"
    echo "\$ $*"
    echo "──────────────────────────────────────────────────────────────"
  } | tee -a "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  {
    echo "[exit=$rc] $title"
  } | tee -a "$LOG"
  return $rc
}

expect() {
  # expect "<验收项>" <期望退出码> <实际退出码> [说明]
  local item="$1" want="$2" got="$3" note="${4:-}"
  if [ "$want" = "$got" ]; then
    printf '  ✅ %-28s exit=%s %s\n' "$item" "$got" "$note" | tee -a "$LOG"
    PASS=$((PASS + 1))
  else
    printf '  ❌ %-28s exit=%s（期望 %s） %s\n' "$item" "$got" "$want" "$note" | tee -a "$LOG"
    FAIL=$((FAIL + 1))
  fi
}

echo "== SDD 上下文模块 · 六项必做项自检 ==" | tee -a "$LOG"
echo "时间：$(date -Is)" | tee -a "$LOG"
echo "模块：$MINIMAX_DIR" | tee -a "$LOG"
echo "运行期目录：${SDDCTX_HOME:-未设置}" | tee -a "$LOG"

# 1. 能够运行 --------------------------------------------------------------
run_step "1/6 能够运行：初始化依赖并跑通端到端演示" bash scripts/setup.sh
expect "1 能够运行" 0 $?

run_step "1/6 端到端演示" bash scripts/run_demo.sh
expect "1 端到端演示" 0 $?

# 2. MiniMax 实际参与 -----------------------------------------------------
if [ -s "$RECORDS_DIR/minimax_dev_record.md" ] \
  && grep -q "提供给模型的上下文" "$RECORDS_DIR/minimax_dev_record.md" \
  && grep -q "模型的代码修改过程" "$RECORDS_DIR/minimax_dev_record.md" \
  && grep -q "补丁与提交代码差异的对应关系" "$RECORDS_DIR/minimax_dev_record.md"; then
  echo "  ✅ 2 MiniMax 实际参与        记录含上下文/模型原文/差异对应" | tee -a "$LOG"
  PASS=$((PASS + 1))
else
  echo "  ❌ 2 MiniMax 实际参与        记录缺关键小节" | tee -a "$LOG"
  FAIL=$((FAIL + 1))
fi

# 3. 上下文正确（含规格更新后重新导入）------------------------------------
run_step "3/6 规格更新并重新导入后使用更新内容" bash scripts/spec_update_check.sh
expect "3 上下文正确" 0 $?

# 4. 数据库实际参与 -------------------------------------------------------
if [ -s "$RECORDS_DIR/db_query_record.md" ] \
  && grep -q "SELECT" "$RECORDS_DIR/db_query_record.md" \
  && grep -q "命中" "$RECORDS_DIR/db_query_record.md"; then
  echo "  ✅ 4 数据库实际参与        seekdb 查询记录含真实 SQL 与命中行数" | tee -a "$LOG"
  PASS=$((PASS + 1))
else
  echo "  ❌ 4 数据库实际参与        查询记录缺失" | tee -a "$LOG"
  FAIL=$((FAIL + 1))
fi

# 5. 状态能够复用 ---------------------------------------------------------
# 顺序要紧：先清空作用域绑定（从空状态开始）→ 再跑一遍流程写入状态 →
# 最后用一个**新进程**读取，证明重启模块后状态可读且被后续上下文使用。
run_step "5/6 清空作用域绑定（从空状态开始）" bash -c "
  cd '$MINIMAX_DIR' && '$PYTHON' -m sddctx reset-state"
expect "5a 从空状态开始" 0 $?

run_step "5/6 保存任务状态到 PowerContext" bash -c "
  cd '$MINIMAX_DIR' && '$PYTHON' -m sddctx demo --transport file --recorded '$RECORDS_DIR/minimax_response.json' --task '$TASK_TEXT' --reset"
expect "5b 保存任务状态" 0 $?

run_step "5/6 新进程读取并复用保存的状态" bash -c "
  cd '$MINIMAX_DIR' && '$PYTHON' -m sddctx resume --task-id T-1"
expect "5c 重启后读取状态" 0 $?

# 6. 代码修改有效 ---------------------------------------------------------
run_step "6/6 修改前失败 / 修改后通过 / 回归前后均通过" bash scripts/verify_before_after.sh
expect "6 代码修改有效" 0 $?

# 快照与前后差异（提交材料的一部分）
run_step "附加：保存修改后快照并生成前后差异" bash -c "
  cd '$MINIMAX_DIR' && '$PYTHON' -m sddctx snapshot --name after"
expect "附加 前后差异" 0 $?

# 模块自身的单元测试
run_step "附加：sddctx 模块单元测试" "$VENV_DIR/bin/python" -m pytest tests -q
expect "附加 模块单元测试" 0 $?

{
  echo
  echo "=============================================================="
  echo "自检结果：通过 $PASS 项，未通过 $FAIL 项"
  echo "完整日志：$LOG"
  echo "=============================================================="
} | tee -a "$LOG"

[ "$FAIL" -eq 0 ]
