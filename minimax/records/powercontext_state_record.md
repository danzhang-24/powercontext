# PowerContext 状态写入与复用记录

- 任务编号：T-1
- 记录时间：2026-10-28T16:42:05+00:00
- 接入方式：HTTP API，Server 地址 http://127.0.0.1:8000
- 逻辑作用域：sddctx:order-discount
- 实际作用域：scp_2cjvwq9x18ajg128q9hcgrkvjs

## 1. 写入（POST /v1/memory/remember）

保存的内容：

```text
sddctx-state v1
task: T-1
phase: after
updated_at: 2026-10-28T16:42:01+00:00
done:
- 导入资料：规格 4 条 / 代码 7 个 / 测试 10 条
- MiniMax 完成代码修改：src/order_discount/engine.py
pending:
artifacts:
- records/minimax_dev_record.md
- records/db_query_record.md
verifications:
- phase=before suite=target exit_code=1 passed=0 failed=4 errored=0 code_version=f7971538e037+content:00421e725ebb summary=4 failed, 6 deselected in 0.12s
- phase=before suite=regression exit_code=0 passed=6 failed=0 errored=0 code_version=f7971538e037+content:00421e725ebb summary=6 passed, 4 deselected in 0.06s
- phase=after suite=target exit_code=0 passed=4 failed=0 errored=0 code_version=f7971538e037+content:e168b3b33781 summary=4 passed, 6 deselected in 0.11s
- phase=after suite=regression exit_code=0 passed=6 failed=0 errored=0 code_version=f7971538e037+content:e168b3b33781 summary=6 passed, 4 deselected in 0.07s
```

服务端返回：

```json
{
  "memory": {
    "family": "memory",
    "artifact_id": "memory",
    "revision": 1
  },
  "entry": {
    "citation": {
      "memory_ref": {
        "family": "memory",
        "artifact_id": "memory",
        "revision": 1
      },
      "entry_id": "mem_ent_9e5486ffe35b4aa4b224dfcfd3c33a3a",
      "entry_version_id": "mem_ver_dfdee8c953a74bc29979e50b17da52ee"
    },
    "version": 1,
    "kind": "sddctx.task_state",
    "text": "sddctx-state v1\ntask: T-1\nphase: after\nupdated_at: 2026-10-28T16:42:01+00:00\ndone:\n- 导入资料：规格 4 条 / 代码 7 个 / 测试 10 条\n- MiniMax 完成代码修改：src/order_discount/engine.py\npending:\nartifacts:\n- records/minimax_dev_record.md\n- records/db_query_record.md\nverifications:\n- phase=before suite=target exit_code=1 passed=0 failed=4 errored=0 code_version=f7971538e037+content:00421e725ebb summary=4 failed, 6 deselected in 0.12s\n- phase=before suite=regression exit_code=0 passed=6 failed=0 errored=0 code_version=f7971538e037+content:00421e725ebb summary=6 passed, 4 deselected in 0.06s\n- phase=after suite=target exit_code=0 passed=4 failed=0 errored=0 code_version=f7971538e037+content:e168b3b33781 summary=4 passed, 6 deselected in 0.11s\n- phase=after suite=regression exit_code=0 passed=6 failed=0 errored=0 code_version=f7971538e037+content:e168b3b33781 summary=6 passed, 4 deselected in 0.07s",
    "state": "active",
    "source_refs": [],
    "artifact_refs": []
  }
}
```

## 2. 模块重启后复用（POST /v1/memory/search）

重启模块后重新读取到的状态：

```text
sddctx-state v1
task: T-1
phase: after
updated_at: 2026-10-28T16:42:01+00:00
done:
- 导入资料：规格 4 条 / 代码 7 个 / 测试 10 条
- MiniMax 完成代码修改：src/order_discount/engine.py
pending:
artifacts:
- records/minimax_dev_record.md
- records/db_query_record.md
verifications:
- phase=before suite=target exit_code=1 passed=0 failed=4 errored=0 code_version=f7971538e037+content:00421e725ebb summary=4 failed, 6 deselected in 0.12s
- phase=before suite=regression exit_code=0 passed=6 failed=0 errored=0 code_version=f7971538e037+content:00421e725ebb summary=6 passed, 4 deselected in 0.06s
- phase=after suite=target exit_code=0 passed=4 failed=0 errored=0 code_version=f7971538e037+content:e168b3b33781 summary=4 passed, 6 deselected in 0.11s
- phase=after suite=regression exit_code=0 passed=6 failed=0 errored=0 code_version=f7971538e037+content:e168b3b33781 summary=6 passed, 4 deselected in 0.07s
```

该状态被用于后续上下文组装（见 minimax_dev_record.md 的上下文小节）。

