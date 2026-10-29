#!/usr/bin/env bash
# 各脚本共用的路径与运行环境。
set -euo pipefail

MINIMAX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 运行期目录配置由 scripts/setup.sh 生成（嵌入式 seekdb 必须在本地文件系统上）。
# 这里 source 进来，让所有脚本共用同一个可用的运行期目录。
if [ -f "$MINIMAX_DIR/scripts/runtime.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$MINIMAX_DIR/scripts/runtime.env"
  set +a
fi
PROJECT_DIR="$MINIMAX_DIR/demo_project"
RECORDS_DIR="$MINIMAX_DIR/records"
LOGS_DIR="$PROJECT_DIR/logs"

# sddctx 使用的虚拟环境（setup.sh 创建）。
VENV_DIR="${SDDCTX_VENV:-$MINIMAX_DIR/.venv}"
# PowerContext Server 使用的虚拟环境（setup.sh 创建）。
PC_VENV_DIR="${SDDCTX_PC_VENV:-$MINIMAX_DIR/.venv-powercontext}"

if [ -x "$VENV_DIR/bin/python" ]; then
  PYTHON="$VENV_DIR/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

# PowerContext Server 地址与作用域。
PC_URL="${POWERCONTEXT_SERVER_URL:-http://127.0.0.1:8000}"
SCOPE_ID="${SDDCTX_SCOPE_ID:-sddctx:order-discount}"

# 演示任务描述：改什么 + 哪些原有行为必须保持。
TASK_TEXT="${SDDCTX_TASK:-让满减门槛只按商品小计计算，并排除含易碎品的订单}"

# 传给 sddctx 的公共参数。
sddctx() {
  (cd "$MINIMAX_DIR" && "$PYTHON" -m sddctx --powercontext-url "$PC_URL" --scope-id "$SCOPE_ID" "$@")
}

log() {
  printf '\n=== %s ===\n' "$*"
}

ensure_server() {
  # 确保 PowerContext Server 可用；不可用时尝试用本地环境启动。
  if curl -fsS "$PC_URL/health/live" >/dev/null 2>&1; then
    return 0
  fi
  if [ ! -x "$PC_VENV_DIR/bin/powercontext" ]; then
    echo "未找到 PowerContext Server（$PC_VENV_DIR/bin/powercontext）。" >&2
    echo "请先执行 bash scripts/setup.sh" >&2
    return 1
  fi
  local env_file="$MINIMAX_DIR/scripts/powercontext.env"
  log "启动 PowerContext Server（$PC_URL）"
  (
    cd "$MINIMAX_DIR"
    setsid nohup "$PC_VENV_DIR/bin/powercontext" server run --env-file "$env_file" \
      > "$MINIMAX_DIR/runtime/powercontext.log" 2>&1 < /dev/null &
  )
  for _ in $(seq 1 60); do
    if curl -fsS "$PC_URL/health/live" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "PowerContext Server 启动超时，请查看 $MINIMAX_DIR/runtime/powercontext.log" >&2
  return 1
}
