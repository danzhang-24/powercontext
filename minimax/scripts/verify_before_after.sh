#!/usr/bin/env bash
# 复现"同一组目标功能测试：修改前因目标行为未实现而失败，修改后全部通过"，
# 同时确认相关回归测试修改前后都通过。
#
# 流程：
#   1. 把工程重置为修改前状态；
#   2. 跑 target / regression，记录命令、退出码、代码版本与输出；
#   3. 用模块自身的补丁应用逻辑落上 MiniMax 给出的补丁；
#   4. 再跑一次 target / regression；
#   5. 校验四组结果是否符合预期，不符合则以非零码退出。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

TRANSPORT="${SDDCTX_TRANSPORT:-file}"
RECORDED="$RECORDS_DIR/minimax_response.json"
mkdir -p "$LOGS_DIR"

log "步骤 0：重置为修改前状态"
bash "$MINIMAX_DIR/scripts/reset_demo.sh"

log "步骤 1：修改前运行测试"
set +e
sddctx verify --phase before --suite target --log-dir "$LOGS_DIR"
BEFORE_TARGET_RC=$?
sddctx verify --phase before --suite regression --log-dir "$LOGS_DIR"
BEFORE_REGRESSION_RC=$?
set -e

log "步骤 2：应用 MiniMax 给出的补丁（transport=$TRANSPORT）"
if [ "$TRANSPORT" = "file" ]; then
  sddctx apply --transport file --recorded "$RECORDED"
else
  sddctx apply --transport "$TRANSPORT"
fi

log "步骤 3：修改后运行测试"
set +e
sddctx verify --phase after --suite target --log-dir "$LOGS_DIR"
AFTER_TARGET_RC=$?
sddctx verify --phase after --suite regression --log-dir "$LOGS_DIR"
AFTER_REGRESSION_RC=$?
set -e

log "步骤 4：校验"
FAILED=0
check() {
  local name="$1" actual="$2" expected="$3"
  if [ "$actual" = "$expected" ]; then
    printf '  [OK]   %-28s 退出码=%s（期望 %s）\n' "$name" "$actual" "$expected"
  else
    printf '  [FAIL] %-28s 退出码=%s（期望 %s）\n' "$name" "$actual" "$expected"
    FAILED=1
  fi
}
check "修改前 target（应失败）" "$BEFORE_TARGET_RC" "1"
check "修改前 regression（应通过）" "$BEFORE_REGRESSION_RC" "0"
check "修改后 target（应通过）" "$AFTER_TARGET_RC" "0"
check "修改后 regression（应通过）" "$AFTER_REGRESSION_RC" "0"

# 修改前的失败必须是"功能断言不成立"，而不是缺依赖、无法启动等环境错误。
if grep -qE "AssertionError" "$LOGS_DIR/before-target.log"; then
  printf '  [OK]   修改前的失败是功能断言不成立（AssertionError）\n'
else
  printf '  [FAIL] 修改前没有看到 AssertionError，可能属于环境错误\n'
  FAILED=1
fi
if grep -qE "ModuleNotFoundError|ImportError|INTERNALERROR|UsageError" "$LOGS_DIR/before-target.log"; then
  printf '  [FAIL] 修改前的失败疑似环境错误（缺依赖/无法启动）\n'
  FAILED=1
else
  printf '  [OK]   修改前没有环境类错误\n'
fi

# 修改前后必须使用同一组测试文件。
if cmp -s "$LOGS_DIR/before-target.log" "$LOGS_DIR/after-target.log"; then
  printf '  [WARN] 修改前后测试日志完全相同，请确认测试确实跑过\n'
fi

log "日志目录：$LOGS_DIR"
if [ "$FAILED" -ne 0 ]; then
  echo "校验未通过。" >&2
  exit 1
fi
echo "校验通过：同一组目标功能测试修改前失败、修改后通过，回归测试前后均通过。"
