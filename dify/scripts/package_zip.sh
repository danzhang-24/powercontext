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
# 打包提交物(不含 node_modules 与模型权重,模型用 npm run setup 拉取)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-../dify-cyborg-tiedan.zip}"
rm -f "$OUT"
zip -qr "$OUT" . \
  -x "node_modules/*" -x "assets/models/*" -x "assets/ort/*" \
     -x "*.log" -x ".git/*" -x "package-lock.json.bak"
echo "打包完成: $OUT ($(du -h "$OUT" | cut -f1))"
