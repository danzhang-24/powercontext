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
# 本地调试用:重启 API server(可选切换 seekdb 全文分支模式)
# 用法: scripts/restart_api.sh [raw|keywords|both]
set -uo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-both}"
PIDFILE=/tmp/stepfun-kb-api.pid

if [ -f "$PIDFILE" ]; then
  kill "$(cat "$PIDFILE")" 2>/dev/null || true
  sleep 2
fi

export SEEKDB_MODE="${SEEKDB_MODE:-server}"
export SEEKDB_HOST="${SEEKDB_HOST:-127.0.0.1}"
export SEEKDB_PORT="${SEEKDB_PORT:-2881}"
export SEEKDB_FT_MODE="$MODE"
export PORT="${PORT:-8787}"

setsid node server/src/index.mjs > /tmp/stepfun-kb-api.log 2>&1 < /dev/null &
echo $! > "$PIDFILE"
sleep 8
tail -n 2 /tmp/stepfun-kb-api.log
curl -sS --max-time 8 "http://127.0.0.1:${PORT}/api/health" | head -c 160; echo
