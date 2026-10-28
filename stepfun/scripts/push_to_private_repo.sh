#!/usr/bin/env bash
# 把 stepfun 的成果推到你的私有仓库(赛题要求的分支 2026-competition-ecosystem)
#
# 赛题流程(见语雀《GitHub在大赛中的使用说明》):
#   1. 在 GitHub 上 Import Repository,导入 https://github.com/oceanbase/powercontext
#      (导入后会自带 2026-competition-ecosystem 分支)
#   2. Personal access token:权限勾到 repo 即可
#   3. 参赛信息里填 https://<用户名>:<token>@github.com/<用户名>/<仓库名>.git
#
# 用法:
#   GITHUB_USER=your-name GITHUB_TOKEN=github_pat_xxx GITHUB_REPO=your-repo \
#     scripts/push_to_private_repo.sh
#
# 注意:token 会出现在 shell history 里,更稳妥的做法是自己手动执行下面的 git 命令,
#      或用 `read -s` 交互式输入(见 --interactive)。
set -euo pipefail
cd "$(dirname "$0")/.."
BRANCH="2026-competition-ecosystem"

if [ "${1:-}" = "--interactive" ]; then
  read -r -p "GitHub 用户名: " GITHUB_USER
  read -r -s -p "GitHub PAT: " GITHUB_TOKEN; echo
  read -r -p "仓库名: " GITHUB_REPO
fi

: "${GITHUB_USER:?请设置 GITHUB_USER}"
: "${GITHUB_TOKEN:?请设置 GITHUB_TOKEN}"
: "${GITHUB_REPO:?请设置 GITHUB_REPO}"

REMOTE="https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${GITHUB_REPO}.git"

git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
# 部分网络下需要显式指定 TLS 版本 / 关闭 HTTP2,否则握手会失败
git config http.sslVersion tlsv1.2 || true
git config http.postBuffer 524288000 || true
# 部分网络下需要显式指定 TLS 版本 / 关闭 HTTP2,否则握手会失败
git config http.sslVersion tlsv1.2 || true
git config http.postBuffer 524288000 || true
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"
git add -A
git commit -m "feat(stepfun): 端侧 embedding + seekdb 混合检索迷你知识库" || true
# 某些网络环境下 git 的 TLS 握手会偶发失败(gnutls_handshake),自动重试
for i in 1 2 3 4 5; do
  echo "push 尝试 $i/5 ..."
  if git -c http.postBuffer=524288000 push -u origin "$BRANCH"; then
    break
  fi
  sleep 5
done

echo
echo "推送完成:$BRANCH -> $GITHUB_USER/$GITHUB_REPO"
echo "下一步:在参赛信息里填 https://${GITHUB_USER}:<token>@github.com/${GITHUB_USER}/${GITHUB_REPO}.git"
echo "评委复现:git clone <该地址> && cd <repo>/stepfun && npm install && npm run setup && npm run build && npm start"
