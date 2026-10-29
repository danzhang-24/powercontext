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
# 启动本地 seekdb server(单节点 OceanBase seekdb)
#
# 依赖:seekdb 服务端安装包(官方 release 的 deb/rpm/tar 包均可)
#   https://github.com/oceanbase/seekdb/releases
#
# 用法:
#   SEEKDB_BIN=/opt/seekdb/usr/bin/seekdb scripts/start_seekdb.sh
#
# 说明:
#   - 数据目录必须放在本地文件系统上。NFS / 对象存储挂载下 seekdb 的
#     日志块直写(O_DIRECT)会失败,表现为 "io_adapter pwrite failed"。
#   - 端口默认 2881(MySQL 协议),seekdb-js 用 server 模式连接。
set -euo pipefail

SEEKDB_BIN="${SEEKDB_BIN:-seekdb}"
SEEKDB_BASE_DIR="${SEEKDB_BASE_DIR:-/var/lib/seekdb}"
SEEKDB_PORT="${SEEKDB_PORT:-2881}"
SEEKDB_LOG_LEVEL="${SEEKDB_LOG_LEVEL:-WARN}"

mkdir -p "$SEEKDB_BASE_DIR"

echo "[start_seekdb] bin=$SEEKDB_BIN base-dir=$SEEKDB_BASE_DIR port=$SEEKDB_PORT"

exec "$SEEKDB_BIN" \
  --nodaemon \
  --base-dir="$SEEKDB_BASE_DIR" \
  --data-dir="$SEEKDB_BASE_DIR/store" \
  --redo-dir="$SEEKDB_BASE_DIR/store/redo" \
  --port="$SEEKDB_PORT" \
  --log-level="$SEEKDB_LOG_LEVEL"
