#!/usr/bin/env bash
# 干净环境复现验证:模拟评委从零开始跑
#
#   1. 全新 clone(用本仓库当源)
#   2. npm install        (验证 .npmrc 的两个 workaround 仍然有效)
#   3. npm run setup      (拉模型 + 拷贝 onnxruntime-web 运行时)
#   4. npm run build      (构建前端)
#   5. npm start          (起 API,连本机已运行的 seekdb server)
#   6. node scripts/e2e.mjs (真实浏览器跑通全流程)
#
# 用法: scripts/cleanroom_check.sh [工作目录]
set -euo pipefail
cd "$(dirname "$0")/.."
WORK="${1:-/var/tmp/cleanroom}"
SRC="$(pwd)"

echo "== 1/6 全新 clone =="
rm -rf "$WORK"
mkdir -p "$WORK"
git clone -q --depth 1 --branch 2026-competition-ecosystem "file://$SRC/../" "$WORK/repo" 2>/dev/null || {
  # 上面的路径不是 git 仓库时,退化为直接拷贝工作树
  mkdir -p "$WORK/repo"
  (cd "$SRC/.." && tar cf - --exclude=node_modules --exclude=dist --exclude=models --exclude=ort --exclude=.git .) | (cd "$WORK/repo" && tar xf -)
}
cd "$WORK/repo/stepfun"
echo "   clone 到 $WORK/repo"

echo "== 2/6 npm install =="
npm install --silent 2>&1 | tail -3

echo "== 3/6 npm run setup(模型 + ort 运行时)==="
npm run setup 2>&1 | tail -4

echo "== 4/6 npm run build =="
npm run build 2>&1 | tail -3

echo "== 5/6 npm start =="
PORT=8799 SEEKDB_MODE=server SEEKDB_HOST=127.0.0.1 SEEKDB_PORT=2881 \
  SEEKDB_DATABASE=cleanroom_kb setsid node server/src/index.mjs > "$WORK/api.log" 2>&1 < /dev/null &
API_PID=$!
sleep 12
curl -sS --max-time 10 http://127.0.0.1:8799/api/health || { echo "   API 启动失败"; tail -20 "$WORK/api.log"; exit 1; }
echo

echo "== 6/6 e2e(真实浏览器)==="
APP_URL=http://127.0.0.1:8799/ node scripts/e2e.mjs --shot "$WORK/cleanroom-e2e.png" 2>&1 | tail -12

kill "$API_PID" 2>/dev/null || true
echo
echo "干净环境复现验证通过 ✅"
