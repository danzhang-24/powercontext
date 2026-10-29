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
# 服务启停助手(用 pidfile,避免 pkill 误杀)
#   scripts/svc.sh start dify|stepfun
#   scripts/svc.sh stop  dify|stepfun
#   scripts/svc.sh status
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${2:-dify}"
case "$NAME" in
  dify)
    RUN_DIR="$PWD"
    CMD="node service/src/index.mjs"
    PIDFILE=/tmp/stepfun-dify.pid
    LOG=/tmp/stepfun-dify.log
    PORT="${SEEKDB_SERVICE_PORT:-8788}"
    ;;
  stepfun)
    RUN_DIR="$PWD/../stepfun"
    CMD="node server/src/index.mjs"
    PIDFILE=/tmp/stepfun-stepfun.pid
    LOG=/tmp/stepfun-stepfun.log
    PORT="${PORT:-8787}"
    ;;
  *) echo "未知服务名: $NAME"; exit 1 ;;
esac

case "${1:-status}" in
  start)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "已在运行 (pid $(cat "$PIDFILE"))"; exit 0
    fi
    cd "$RUN_DIR"
    setsid env SEEKDB_MODE="${SEEKDB_MODE:-server}" SEEKDB_HOST="${SEEKDB_HOST:-127.0.0.1}" \
      SEEKDB_PORT="${SEEKDB_PORT:-2881}" SEEKDB_DATABASE="${SEEKDB_DATABASE:-dify_kb}" \
      SEEKDB_SERVICE_PORT="${SEEKDB_SERVICE_PORT:-8788}" PORT="${PORT:-8787}" \
      $CMD > "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    sleep 12
    echo "started (pid $(cat "$PIDFILE")), log: $LOG"
    tail -3 "$LOG"
    ;;
  restart)
    "$0" stop "$NAME"
    sleep 1
    "$0" start "$NAME"
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null && echo "stopped $(cat "$PIDFILE")"
      rm -f "$PIDFILE"
    else
      echo "未在运行"
    fi
    ;;
  status)
    for p in /tmp/stepfun-dify.pid /tmp/stepfun-stepfun.pid; do
      [ -f "$p" ] && echo "$p -> $(kill -0 "$(cat "$p")" 2>/dev/null && echo alive || echo dead) ($(cat "$p"))"
    done
    curl -sS --max-time 5 "http://127.0.0.1:8788/health" && echo
    curl -sS --max-time 5 "http://127.0.0.1:8787/api/health" && echo
    ;;
esac
