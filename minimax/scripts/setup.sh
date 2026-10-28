#!/usr/bin/env bash
# 准备运行环境：sddctx 依赖 + PowerContext Server 依赖 + 服务端配置。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

log "Python 版本"
python3 -V

log "安装 sddctx 依赖（$VENV_DIR）"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install -r "$MINIMAX_DIR/requirements.txt"

log "安装 PowerContext Server 依赖（$PC_VENV_DIR）"
if [ ! -x "$PC_VENV_DIR/bin/python" ]; then
  python3 -m venv "$PC_VENV_DIR"
fi
"$PC_VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
# pymysql 必须锁 1.1.1，原因见 requirements.txt 的说明。
"$PC_VENV_DIR/bin/python" -m pip install "powercontext==1.2.0" "pymysql==1.1.1"

log "生成 PowerContext Server 配置"
ENV_FILE="$MINIMAX_DIR/scripts/powercontext.env"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<EOF
# PowerContext Server 配置（占位值，按需修改后另存为 .env.local）
POWERCONTEXT_SERVER_HTTP_HOST=127.0.0.1
POWERCONTEXT_SERVER_HTTP_PORT=8000
POWERCONTEXT_SERVER_ACCESS_MODE=disabled
POWERCONTEXT_SERVER_DATABASE_KIND=seekdb
POWERCONTEXT_SERVER_DATABASE_PATH=$MINIMAX_DIR/runtime/powercontext-seekdb
POWERCONTEXT_SERVER_WORKSPACE=$MINIMAX_DIR/runtime/powercontext-workspace
EOF
  echo "已写入 $ENV_FILE"
else
  echo "$ENV_FILE 已存在，保持不变"
fi

mkdir -p "$MINIMAX_DIR/runtime"

log "自检"
"$VENV_DIR/bin/python" -c "import pylibseekdb, pytest; print('pylibseekdb', pylibseekdb.__name__ and 'ok'); print('pytest ok')"
"$PC_VENV_DIR/bin/powercontext" --version

cat <<EOF

环境准备完成。下一步：
  bash scripts/run_demo.sh          # 跑完整演示流程
  bash scripts/verify_before_after.sh  # 单独复现"修改前失败 / 修改后通过"

如需走 MiniMax 官方 HTTP 接口：
  export MINIMAX_API_KEY=sk-xxxxxxxx
  export SDDCTX_TRANSPORT=http
EOF
