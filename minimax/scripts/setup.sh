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

log "探测可用的运行期目录（嵌入式 seekdb 需要支持 O_DIRECT 的本地文件系统）"
RUNTIME_CANDIDATES=(
  "${SDDCTX_HOME:-$MINIMAX_DIR/runtime}"
  "/var/tmp/sddctx-runtime"
  "/opt/sddctx-runtime"
  "${TMPDIR:-/tmp}/sddctx-runtime"
)
RUNTIME_DIR="$("$VENV_DIR/bin/python" "$MINIMAX_DIR/scripts/probe_runtime_dir.py" "${RUNTIME_CANDIDATES[@]}")" || {
  echo "无法找到可运行嵌入式 seekdb 的目录，请用 SDDCTX_HOME 指定本地路径" >&2
  exit 1
}
echo "运行期目录: $RUNTIME_DIR"

log "生成运行期配置"
RUNTIME_ENV="$MINIMAX_DIR/scripts/runtime.env"
cat > "$RUNTIME_ENV" <<EOF
# 由 scripts/setup.sh 生成：运行期数据目录（嵌入式 seekdb 必须在本地文件系统上）
SDDCTX_HOME=$RUNTIME_DIR
POWERCONTEXT_SERVER_DATABASE_PATH=$RUNTIME_DIR/powercontext-seekdb
POWERCONTEXT_SERVER_WORKSPACE=$RUNTIME_DIR/powercontext-workspace
EOF
echo "已写入 $RUNTIME_ENV"

log "生成 PowerContext Server 配置"
ENV_FILE="$MINIMAX_DIR/scripts/powercontext.env"
cat > "$ENV_FILE" <<EOF
# PowerContext Server 配置（占位值，按需修改后另存为 .env.local）
POWERCONTEXT_SERVER_HTTP_HOST=127.0.0.1
POWERCONTEXT_SERVER_HTTP_PORT=8000
POWERCONTEXT_SERVER_ACCESS_MODE=disabled
POWERCONTEXT_SERVER_DATABASE_KIND=seekdb
POWERCONTEXT_SERVER_DATABASE_PATH=$RUNTIME_DIR/powercontext-seekdb
POWERCONTEXT_SERVER_WORKSPACE=$RUNTIME_DIR/powercontext-workspace
EOF
echo "已写入 $ENV_FILE"

# PowerContext Server 要求 workspace 目录已存在（否则启动时 pydantic 校验直接失败），
# seekdb 数据目录也需要预先建好，避免 server 以 seekdb 模式启动时初始化失败。
mkdir -p "$RUNTIME_DIR/powercontext-workspace" "$RUNTIME_DIR/powercontext-seekdb"

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
