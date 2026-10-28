#!/usr/bin/env bash
# 打包提交物(不含 node_modules 与模型权重,模型用 npm run setup 拉取)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-../dify-cyborg-tiedan.zip}"
rm -f "$OUT"
zip -qr "$OUT" . \
  -x "node_modules/*" -x "assets/models/*" -x "assets/ort/*" \
     -x "*.log" -x ".git/*" -x "package-lock.json.bak"
echo "打包完成: $OUT ($(du -h "$OUT" | cut -f1))"
