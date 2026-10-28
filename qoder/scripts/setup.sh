#!/usr/bin/env bash
# 准备运行环境：应用依赖 + PowerContext Server 依赖 + 服务端配置 + seekdb 表结构。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

log "Python 版本"
python3 -V

# 创建虚拟环境：优先使用 uv（更快），没有 uv 时回退到标准 venv + pip。
create_venv() {
  local venv_dir="$1"
  if [ -x "$venv_dir/bin/python" ]; then
    return 0
  fi
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 "$venv_dir"
  else
    python3 -m venv "$venv_dir"
  fi
}

pip_install() {
  local venv_dir="$1"
  shift
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$venv_dir/bin/python" "$@"
  else
    "$venv_dir/bin/python" -m pip install --upgrade pip >/dev/null
    "$venv_dir/bin/python" -m pip install "$@"
  fi
}

log "安装应用依赖（$VENV_DIR）"
create_venv "$VENV_DIR"
pip_install "$VENV_DIR" -r "$QODER_DIR/requirements.txt"

log "安装 PowerContext Server 依赖（$PC_VENV_DIR）"
create_venv "$PC_VENV_DIR"
# pymysql 必须锁 1.1.1，原因见 requirements-powercontext.txt 的说明。
pip_install "$PC_VENV_DIR" -r "$QODER_DIR/requirements-powercontext.txt"

log "生成 PowerContext Server 配置"
ENV_FILE="$QODER_DIR/scripts/powercontext.env"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<EOF
# PowerContext Server 配置（占位值，按需修改后另存为 .env.local）
POWERCONTEXT_SERVER_HTTP_HOST=127.0.0.1
POWERCONTEXT_SERVER_HTTP_PORT=8100
POWERCONTEXT_SERVER_ACCESS_MODE=disabled
POWERCONTEXT_SERVER_DATABASE_KIND=seekdb
POWERCONTEXT_SERVER_DATABASE_PATH=runtime/powercontext-seekdb
POWERCONTEXT_SERVER_WORKSPACE=runtime/powercontext-workspace
EOF
  echo "已写入 $ENV_FILE"
else
  echo "$ENV_FILE 已存在，保持不变"
fi

mkdir -p "$RUNTIME_DIR/powercontext-workspace" "$RUNTIME_DIR/powercontext-seekdb" "$RECORDS_DIR"

log "启动本地模型服务与 PowerContext Server"
ensure_model_server
ensure_powercontext

log "在 seekdb 上建库、建表并创建全文索引与向量索引"
(
  cd "$QODER_DIR"
  "$VENV_DIR/bin/python" - <<'PY'
from paperpocket.config import load_settings
from paperpocket.service import PaperPocket

app = PaperPocket(load_settings())
with app:
    app.prepare_schema()
    print("seekdb 版本：", app.db.server_version())
    print("表结构准备完成：papers / paper_chunks / reading_log / briefs")
PY
)

log "把本地模型服务注册到 seekdb（AI_EMBED / AI_COMPLETE）"
ensure_model_server
paperpocket setup-ai

log "自检"
"$VENV_DIR/bin/python" -c "import pymysql, pytest; print('pymysql', pymysql.__version__); print('pytest ok')"
"$PC_VENV_DIR/bin/powercontext" --version
curl -fsS "$PC_URL/health/live" && echo "　PowerContext Server 正常"
curl -fsS "$MODEL_SERVER_URL/models" >/dev/null && echo "　本地模型服务正常"

cat <<EOF

环境准备完成。下一步：
  bash scripts/run_demo.sh     # 跑完整演示流程并产出记录
  bash scripts/verify.sh       # 单独复现验收要点

提示：seekdb 地址可通过 PAPERPOCKET_DB_HOST / PAPERPOCKET_DB_PORT 覆盖，
      默认 $DB_HOST:$DB_PORT。
EOF
