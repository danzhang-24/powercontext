#!/usr/bin/env bash
# 干净环境复现验证:模拟评委从零开始跑 dify 这一份
#
#   1. 全新 clone(用本仓库当源,只带 git 里的内容)
#   2. npm install --legacy-peer-deps  (验证 .npmrc 的 workaround 仍然有效)
#   3. npm run setup        (拉模型权重 + onnxruntime-web wasm)
#   4. npm run seed         (幂等写入 12 张设定卡)
#   5. npm start            (起服务,连本机已运行的 seekdb server)
#   6. node scripts/verify_app.mjs  (端到端 9 项)
#
# 用法: scripts/cleanroom_check.sh [工作目录]
set -euo pipefail
cd "$(dirname "$0")/.."
WORK="${1:-/var/tmp/cleanroom-dify}"
SRC="$(pwd)"
PORT="${CLEANROOM_PORT:-8790}"

echo "== 1/6 全新 clone =="
rm -rf "$WORK"
mkdir -p "$WORK"
git clone -q --depth 1 --branch 2026-competition-ecosystem "file://$SRC/../" "$WORK/repo" 2>/dev/null || {
  mkdir -p "$WORK/repo"
  (cd "$SRC/.." && tar cf - --exclude=node_modules --exclude=assets --exclude=dist --exclude=models --exclude=ort --exclude=.git .) | (cd "$WORK/repo" && tar xf -)
}
cd "$WORK/repo/dify"
echo "   clone 到 $WORK/repo/dify"

echo "== 2/6 npm install =="
npm install --silent --legacy-peer-deps 2>&1 | tail -3

echo "== 3/6 npm run setup =="
npm run setup 2>&1 | tail -5

echo "== 4/6 npm run seed =="
SEEKDB_DATABASE="${SEEKDB_DATABASE:-dify_kb}" npm run seed 2>&1 | tail -3

echo "== 5/6 npm start =="
SEEKDB_SERVICE_PORT="$PORT" setsid env SEEKDB_SERVICE_PORT="$PORT" node service/src/index.mjs > "$WORK/service.log" 2>&1 < /dev/null &
SVC_PID=$!
for i in $(seq 1 40); do
  sleep 2
  if curl -sS --max-time 3 -H "Authorization: Bearer ${SEEKDB_API_KEY:-dify-2026-stepfun}" "http://127.0.0.1:$PORT/health" > /dev/null 2>&1; then break; fi
done
curl -sS --max-time 5 -H "Authorization: Bearer ${SEEKDB_API_KEY:-dify-2026-stepfun}" "http://127.0.0.1:$PORT/health"; echo

echo "== 6/6 端到端验证 =="
node scripts/validate_dsl.mjs | tail -2
node scripts/verify_app.mjs "http://127.0.0.1:$PORT" | tail -12

kill "$SVC_PID" 2>/dev/null || true
echo
echo "干净环境复现验证完成,日志: $WORK/service.log"
