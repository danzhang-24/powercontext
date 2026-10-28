#!/usr/bin/env bash
# 验证"更新规格并重新导入后，模块使用更新后的内容"。
#
# 做法：
#   1. 备份规格文件；
#   2. 修改 SPEC-DISC-003 的规则文本（追加一条新的验收约束）；
#   3. 用独立的工作目录重新导入，并重新检索上下文；
#   4. 检查检索结果里出现的是更新后的规则文本；
#   5. 还原规格文件。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

SPEC="$PROJECT_DIR/specs/order_discount.spec.md"
WORK="$MINIMAX_DIR/runtime/speccheck"
OUT="$RECORDS_DIR/spec_update_record.md"
NEW_MARK="易碎品订单即使满 600 元也不享受任何满减减免"
OLD_MARK="运费不改变这一结论"

log "备份规格文件"
BACKUP="$(mktemp)"
cp "$SPEC" "$BACKUP"
restore() {
  cp "$BACKUP" "$SPEC"
  rm -f "$BACKUP"
}
trap restore EXIT

log "修改 SPEC-DISC-003 的规则文本"
"$PYTHON" - "$SPEC" "$OLD_MARK" "$NEW_MARK" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
old_mark, new_mark = sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")
if old_mark not in text:
    raise SystemExit(f"规格里找不到锚点：{old_mark}")
text = text.replace(old_mark, f"{old_mark}；{new_mark}", 1)
path.write_text(text, encoding="utf-8")
print("规格已更新")
PY

log "重新导入（独立工作目录）"
rm -rf "$WORK"
sddctx --work-dir "$WORK" import-materials > /dev/null

log "重新检索上下文"
sddctx --work-dir "$WORK" context --task "$TASK_TEXT" --out "$WORK/context.md" > /dev/null

log "校验检索结果用的是更新后的规则"
"$PYTHON" - "$WORK/context.md" "$NEW_MARK" "$OUT" <<'PY'
import pathlib, sys
context_path, new_mark, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
text = pathlib.Path(context_path).read_text(encoding="utf-8")
found = new_mark in text
lines = [
    "# 规格更新后的重新导入验证",
    "",
    "本文件验证验收项：更新样例中的规格并重新导入后，模块应使用更新后的内容，",
    "而不是始终返回固定答案。",
    "",
    "## 操作",
    "",
    "1. 备份 `demo_project/specs/order_discount.spec.md`；",
    "2. 在 SPEC-DISC-003 的规则末尾追加约束：",
    "",
    f"   > {new_mark}",
    "",
    "3. 用独立工作目录执行 `import-materials` 重新导入；",
    "4. 执行 `context` 重新检索；",
    "5. 检查检索输出中出现的是更新后的规则文本；",
    "6. 还原规格文件。",
    "",
    "## 结果",
    "",
    f"- 检索输出中出现新增约束：**{'是' if found else '否'}**",
    "- 重新检索到的 SPEC-DISC-003 规则原文：",
]
text_lines = text.splitlines()
start = next((i for i, line in enumerate(text_lines) if "SPEC-DISC-003" in line), -1)
rule = next(
    (line.strip() for line in text_lines[start + 1:] if line.strip().startswith("- 规则：")),
    "（未找到）",
)
lines += ["", f"  {rule}", ""]
lines += [
    "## 重置方法",
    "",
    "规格文件在脚本结束时已自动还原；如需手工还原，用 `snapshots/before/order_discount.spec.md` 覆盖即可：",
    "",
    "```bash",
    "cp demo_project/snapshots/before/order_discount.spec.md demo_project/specs/order_discount.spec.md",
    "```",
    "",
]
pathlib.Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
print("记录已写入", out_path)
if not found:
    raise SystemExit("检索结果里没有出现更新后的规则文本")
print("校验通过：重新导入后使用的是更新后的规格内容")
PY

log "还原规格文件"
restore
trap - EXIT
echo "规格已还原。记录：$OUT"
