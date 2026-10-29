#!/usr/bin/env python3
"""探测一个可以跑嵌入式 seekdb 的运行期目录。

嵌入式 seekdb(pylibseekdb)底层用 O_DIRECT 直写，**NFS / 部分网络文件系统上会
打不开库**（报 ``seekdb_open failed: code=-1``）。所以运行期目录必须落在本地
文件系统上。

用法：
    python scripts/probe_runtime_dir.py <候选目录> [...]

逐个候选目录试开一个临时库，打印第一个可用的目录；都不可用时打印错误并以非零码退出。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile


def probe(path: str) -> tuple[bool, str]:
    """试开一个临时 seekdb 库，返回 (是否可用, 说明)。"""
    os.makedirs(path, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="sddctx-probe-", dir=path)
    try:
        import pylibseekdb

        instance = pylibseekdb.open(db_dir=tmp)
        conn = pylibseekdb.connect(database="test")
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS probe_t (a INT)")
        cur.execute("INSERT INTO probe_t VALUES (1)")
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM probe_t")
        cur.fetchall()
        del instance
        return True, "可用"
    except Exception as exc:  # noqa: BLE001 - 探测阶段要吞掉所有异常
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str]) -> int:
    candidates = argv[1:] or ["/var/tmp/sddctx-runtime"]
    tried: list[str] = []
    for cand in candidates:
        ok, why = probe(cand)
        tried.append(f"  - {cand}: {why}")
        if ok:
            print(cand)
            return 0
    print("没有一个候选目录可以运行嵌入式 seekdb：", file=sys.stderr)
    print("\n".join(tried), file=sys.stderr)
    print(
        "\n嵌入式 seekdb 需要支持 O_DIRECT 的本地文件系统；\n"
        "请用 SDDCTX_HOME 指定一个本地路径（例如 /var/tmp/sddctx-runtime）后重试。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
