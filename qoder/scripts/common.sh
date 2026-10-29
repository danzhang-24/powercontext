#!/usr/bin/env bash
# 各脚本共用的路径与运行环境。
set -euo pipefail

# qoder/ 目录（模块根）。
QODER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECORDS_DIR="$QODER_DIR/records"
RUNTIME_DIR="$QODER_DIR/runtime"
CORPUS_DIR="$QODER_DIR/corpus"

# 应用虚拟环境（setup.sh 创建）。
VENV_DIR="${PAPERPOCKET_VENV:-$QODER_DIR/.venv}"
# PowerContext Server 虚拟环境（setup.sh 创建）。
PC_VENV_DIR="${PAPERPOCKET_PC_VENV:-$QODER_DIR/.venv-powercontext}"

if [ -x "$VENV_DIR/bin/python" ]; then
  PYTHON="$VENV_DIR/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

# seekdb（MySQL 协议）连接参数。
DB_HOST="${PAPERPOCKET_DB_HOST:-127.0.0.1}"
DB_PORT="${PAPERPOCKET_DB_PORT:-5881}"
DB_NAME="${PAPERPOCKET_DB_NAME:-paperpocket}"

# PowerContext Server 地址与作用域。
PC_URL="${PAPERPOCKET_POWERCONTEXT_URL:-http://127.0.0.1:8100}"
SCOPE_ID="${PAPERPOCKET_SCOPE_ID:-paperpocket:research}"

# 本地 OpenAI 兼容模型服务（seekdb 的 AI_EMBED / AI_COMPLETE 会去请求它）。
MODEL_SERVER_HOST="${PAPERPOCKET_MODEL_SERVER_HOST:-127.0.0.1}"
MODEL_SERVER_PORT="${PAPERPOCKET_MODEL_SERVER_PORT:-8300}"
MODEL_SERVER_URL="${PAPERPOCKET_MODEL_SERVER_URL:-http://$MODEL_SERVER_HOST:$MODEL_SERVER_PORT/v1}"

# 演示检索词。
DEMO_QUERY="${PAPERPOCKET_DEMO_QUERY:-图神经网络 消息传递 邻居聚合}"

log() {
  printf '\n=== %s ===\n' "$*"
}

# 调用 PaperPocket CLI。
paperpocket() {
  (cd "$QODER_DIR" && "$PYTHON" -m paperpocket \
    --db-host "$DB_HOST" --db-port "$DB_PORT" --db-name "$DB_NAME" \
    --powercontext-url "$PC_URL" --scope-id "$SCOPE_ID" "$@")
}

# 确保本地模型服务可用（seekdb 的 AI 函数依赖它）。
ensure_model_server() {
  if curl -fsS "$MODEL_SERVER_URL/models" >/dev/null 2>&1; then
    return 0
  fi
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "未找到应用虚拟环境（$VENV_DIR/bin/python），请先执行 bash scripts/setup.sh" >&2
    return 1
  fi
  log "启动本地模型服务（$MODEL_SERVER_URL）"
  mkdir -p "$RUNTIME_DIR"
  (
    cd "$QODER_DIR"
    setsid nohup "$VENV_DIR/bin/python" -m paperpocket.model_server \
      --host "$MODEL_SERVER_HOST" --port "$MODEL_SERVER_PORT" \
      --embed-dim "${PAPERPOCKET_EMBED_DIM:-64}" \
      --request-log "$RUNTIME_DIR/model_server_requests.log" \
      > "$RUNTIME_DIR/model_server.log" 2>&1 < /dev/null &
  )
  for _ in $(seq 1 60); do
    if curl -fsS "$MODEL_SERVER_URL/models" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "本地模型服务启动超时，请查看 $RUNTIME_DIR/model_server.log" >&2
  return 1
}

# 确保 PowerContext Server 可用。
ensure_powercontext() {
  if curl -fsS "$PC_URL/health/live" >/dev/null 2>&1; then
    return 0
  fi
  if [ ! -x "$PC_VENV_DIR/bin/powercontext" ]; then
    echo "未找到 PowerContext Server（$PC_VENV_DIR/bin/powercontext），请先执行 bash scripts/setup.sh" >&2
    return 1
  fi
  local env_file="$QODER_DIR/scripts/powercontext.env"
  log "启动 PowerContext Server（$PC_URL）"
  mkdir -p "$RUNTIME_DIR/powercontext-workspace" "$RUNTIME_DIR/powercontext-seekdb"
  (
    cd "$QODER_DIR"
    setsid nohup "$PC_VENV_DIR/bin/powercontext" server run --env-file "$env_file" \
      > "$RUNTIME_DIR/powercontext.log" 2>&1 < /dev/null &
  )
  for _ in $(seq 1 90); do
    if curl -fsS "$PC_URL/health/live" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "PowerContext Server 启动超时，请查看 $RUNTIME_DIR/powercontext.log" >&2
  return 1
}
