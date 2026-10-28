"""sddctx 命令行入口。

子命令：

- ``import-materials``：把规格、代码、测试导入 seekdb。
- ``context``：按任务描述检索并输出开发上下文（规格 / 代码 / 测试 / 状态）。
- ``apply``：把上下文交给 MiniMax 生成补丁并应用。
- ``verify``：运行目标功能测试与回归测试，结果写入 seekdb。
- ``save-state``：把任务状态写入 PowerContext。
- ``resume``：读取 PowerContext 中保存的任务状态（模块重启后复用）。
- ``demo``：按题目流程跑完整一遍演示并产出技术使用记录。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import load_settings
from .minimax_client import MiniMaxClient, MiniMaxError
from .pipeline import (
    step_apply,
    step_context,
    step_import,
    step_resume,
    step_save_state,
    step_verify,
    write_db_record,
    write_minimax_record,
    write_state_record,
)
from .reset import reset_project
from .snapshot import capture_snapshot, snapshot_diff
from .store import SeekdbStore
from .task_state import PowerContextError, PowerContextState

DEFAULT_TASK = "让满减门槛只按商品小计计算，并排除含易碎品的订单"


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。"""
    parser = argparse.ArgumentParser(
        prog="sddctx",
        description="SDD 上下文模块：检索规格/代码/测试，驱动 MiniMax 改码，用 PowerContext 复用任务状态。",
    )
    parser.add_argument("--version", action="version", version=f"sddctx {__version__}")
    parser.add_argument("--project", help="演示工程目录（默认 minimax/demo_project）")
    parser.add_argument("--work-dir", help="运行期数据目录（默认 minimax/runtime）")
    parser.add_argument("--powercontext-url", help="PowerContext Server 地址（默认 http://127.0.0.1:8000）")
    parser.add_argument("--scope-id", help="PowerContext 作用域（默认 sddctx:order-discount）")
    parser.add_argument("--records-dir", help="技术使用记录输出目录（默认 minimax/records）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("import-materials", help="导入规格、代码与测试到 seekdb")

    reset_cmd = sub.add_parser("reset", help="把演示工程恢复到修改前状态")
    reset_cmd.add_argument("--project", dest="reset_project", help="演示工程目录")

    sub.add_parser("reset-state", help="丢弃本地作用域绑定，下次从空状态开始")

    snapshot_cmd = sub.add_parser("snapshot", help="把工程当前状态存成快照并生成前后差异")
    snapshot_cmd.add_argument("--name", default="after", help="快照名称（默认 after）")
    snapshot_cmd.add_argument("--diff-out", help="把前后 unified diff 写入该文件")
    snapshot_cmd.add_argument("--project", dest="snapshot_project", help="演示工程目录")

    context_cmd = sub.add_parser("context", help="检索并输出开发上下文")
    context_cmd.add_argument("--task", default=DEFAULT_TASK, help="任务描述")
    context_cmd.add_argument("--task-id", default="T-1", help="任务编号")
    context_cmd.add_argument("--out", help="把上下文写入文件")
    context_cmd.add_argument("--no-state", action="store_true", help="不读取 PowerContext 状态")

    apply_cmd = sub.add_parser("apply", help="调用 MiniMax 生成补丁并应用")
    apply_cmd.add_argument("--task", default=DEFAULT_TASK, help="任务描述")
    apply_cmd.add_argument("--task-id", default="T-1", help="任务编号")
    apply_cmd.add_argument("--transport", default="http", choices=["http", "cli", "file"])
    apply_cmd.add_argument("--model", help="模型名（默认取配置）")
    apply_cmd.add_argument("--recorded", help="transport=file 时使用的响应文件")
    apply_cmd.add_argument("--no-apply", action="store_true", help="只生成补丁，不写文件")

    verify_cmd = sub.add_parser("verify", help="运行测试并记录结果")
    verify_cmd.add_argument("--task-id", default="T-1", help="任务编号")
    verify_cmd.add_argument("--suite", default="all", choices=["target", "regression", "all"])
    verify_cmd.add_argument("--phase", default="after", choices=["before", "after"])
    verify_cmd.add_argument("--log-dir", help="把命令、退出码与测试输出写入该目录")

    save_cmd = sub.add_parser("save-state", help="把任务状态写入 PowerContext")
    save_cmd.add_argument("--task-id", default="T-1", help="任务编号")
    save_cmd.add_argument("--phase", default="after", help="任务阶段")
    save_cmd.add_argument("--done", action="append", default=[], help="已完成事项，可重复")
    save_cmd.add_argument("--pending", action="append", default=[], help="待办事项，可重复")
    save_cmd.add_argument("--artifact", action="append", default=[], help="产出物路径，可重复")

    resume_cmd = sub.add_parser("resume", help="读取 PowerContext 中保存的任务状态")
    resume_cmd.add_argument("--task-id", default="T-1", help="任务编号")

    demo_cmd = sub.add_parser("demo", help="跑完整演示流程并产出记录")
    demo_cmd.add_argument("--task", default=DEFAULT_TASK, help="任务描述")
    demo_cmd.add_argument("--task-id", default="T-1", help="任务编号")
    demo_cmd.add_argument("--transport", default="http", choices=["http", "cli", "file"])
    demo_cmd.add_argument("--model", help="模型名")
    demo_cmd.add_argument("--recorded", help="transport=file 时使用的响应文件")
    demo_cmd.add_argument("--skip-apply", action="store_true", help="跳过模型调用，只跑导入/检索/验证")
    demo_cmd.add_argument("--skip-verify", action="store_true", help="跳过测试")
    demo_cmd.add_argument("--log-dir", help="测试运行日志输出目录（默认 demo_project/logs）")
    demo_cmd.add_argument("--reset", action="store_true", help="先把工程恢复为修改前状态再执行")
    demo_cmd.add_argument("--no-state", action="store_true", help="不读写 PowerContext 状态")

    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行主函数。"""
    args = build_parser().parse_args(argv)
    settings = load_settings(
        project_dir=args.project,
        work_dir=args.work_dir,
        powercontext_url=args.powercontext_url,
        scope_id=args.scope_id,
        records_dir=args.records_dir,
    )
    settings.ensure_dirs()
    state_client = PowerContextState(
        settings.powercontext_url,
        settings.scope_id,
        binding_path=settings.work_dir / "scope.json",
    )

    if args.command == "import-materials":
        return _cmd_import(args, settings)
    if args.command == "reset":
        return _cmd_reset(args, settings)
    if args.command == "reset-state":
        return _cmd_reset_state(args, settings, state_client)
    if args.command == "snapshot":
        return _cmd_snapshot(args, settings)
    if args.command == "context":
        return _cmd_context(args, settings, state_client)
    if args.command == "apply":
        return _cmd_apply(args, settings, state_client)
    if args.command == "verify":
        return _cmd_verify(args, settings)
    if args.command == "save-state":
        return _cmd_save_state(args, settings, state_client)
    if args.command == "resume":
        return _cmd_resume(args, state_client)
    if args.command == "demo":
        return _cmd_demo(args, settings, state_client)
    return 1


def _emit(args: argparse.Namespace, payload: dict, text: str) -> None:
    """按 --json 决定输出形式。"""
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)


def _cmd_import(args: argparse.Namespace, settings) -> int:
    with SeekdbStore(db_dir=settings.db_dir) as store:
        store.create_schema()
        report = step_import(store, settings)
    _emit(args, report.to_dict(), _render_import(report))
    return 0


def _render_import(report) -> str:
    lines = ["资料导入完成（seekdb）"]
    lines.append(f"- 规格条目：{report.spec_count} 条，来源 {', '.join(report.spec_files) or '-'}")
    lines.append(f"- 代码符号：{report.code_symbol_count} 个，来源 {', '.join(report.code_files) or '-'}")
    lines.append(f"- 测试用例：{report.test_case_count} 条，来源 {', '.join(report.test_files) or '-'}")
    return "\n".join(lines)


def _cmd_reset(args: argparse.Namespace, settings) -> int:
    project_dir = Path(args.reset_project).resolve() if args.reset_project else settings.project_dir
    restored = reset_project(project_dir)
    _emit(args, {"project_dir": str(project_dir), "restored": restored},
          f"演示工程已恢复到修改前状态：{', '.join(restored)}")
    return 0


def _cmd_reset_state(args: argparse.Namespace, settings, state_client: PowerContextState) -> int:
    state_client.forget_scope()
    _emit(
        args,
        {"scope_id": settings.scope_id, "binding": str(state_client.binding_path)},
        f"已丢弃作用域绑定（{state_client.binding_path}），下次保存状态时会新建空作用域。",
    )
    return 0


def _cmd_snapshot(args: argparse.Namespace, settings) -> int:
    project_dir = Path(args.snapshot_project).resolve() if args.snapshot_project else settings.project_dir
    captured = capture_snapshot(project_dir, args.name)
    diff = snapshot_diff(project_dir)
    diff_path = Path(args.diff_out) if args.diff_out else project_dir / "patches" / "before-after.patch"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(diff, encoding="utf-8")
    _emit(
        args,
        {"project_dir": str(project_dir), "snapshot": args.name, "files": captured, "diff": str(diff_path)},
        f"已保存快照 {args.name}：{', '.join(captured)}\n前后差异：{diff_path}",
    )
    return 0


def _cmd_context(args: argparse.Namespace, settings, state_client: PowerContextState) -> int:
    with SeekdbStore(db_dir=settings.db_dir) as store:
        store.create_schema()
        bundle = step_context(
            store,
            settings,
            args.task_id,
            args.task,
            None if args.no_state else state_client,
        )
    if args.out:
        Path(args.out).write_text(bundle.to_markdown(), encoding="utf-8")
    _emit(args, bundle.to_dict(), bundle.to_markdown())
    return 0


def _cmd_apply(args: argparse.Namespace, settings, state_client: PowerContextState) -> int:
    with SeekdbStore(db_dir=settings.db_dir) as store:
        store.create_schema()
        bundle = step_context(store, settings, args.task_id, args.task, state_client)
        client = _make_client(args)
        result = step_apply(store, settings, bundle, client, apply_patch=not args.no_apply)
    write_minimax_record(settings, bundle, result)
    payload = result.to_dict()
    payload["context_file"] = str(settings.records_dir / "minimax_dev_record.md")
    text = "\n".join(
        [
            "MiniMax 已返回补丁。",
            f"- 模型：{result.model}",
            f"- 接入方式：{result.transport}",
            f"- 修改文件：{', '.join(result.applied_files) or '（未应用）'}",
            f"- 补丁长度：{len(result.diff)} 字符",
            f"- 记录：{settings.records_dir / 'minimax_dev_record.md'}",
        ]
    )
    _emit(args, payload, text)
    return 0


def _cmd_verify(args: argparse.Namespace, settings) -> int:
    suites = ("target", "regression") if args.suite == "all" else (args.suite,)
    with SeekdbStore(db_dir=settings.db_dir) as store:
        store.create_schema()
        results = step_verify(store, settings, args.task_id, phase=args.phase, suites=suites)
    if args.log_dir:
        for item in results:
            _write_suite_log(Path(args.log_dir), item)
    payload = [item.to_dict() for item in results]
    lines = []
    for item in results:
        lines.append(
            f"[{item.phase}/{item.suite}] exit={item.exit_code} passed={item.passed} "
            f"failed={item.failed} errored={item.errored} — {item.summary}"
        )
    _emit(args, payload, "\n".join(lines))
    return 0 if all(item.exit_code == 0 for item in results) else 1


def _write_suite_log(log_dir: Path, item) -> Path:
    """写出一个测试套件的运行日志。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{item.phase}-{item.suite}.log"
    lines = [
        f"# 阶段：{item.phase}",
        f"# 套件：{item.suite}",
        f"# 命令：{item.command}",
        f"# 退出码：{item.exit_code}",
        f"# 统计：通过 {item.passed}，失败 {item.failed}，错误 {item.errored}",
        f"# 代码版本：{item.code_version}",
        f"# 汇总：{item.summary}",
        "",
        "----- stdout -----",
        item.stdout.rstrip(),
        "",
        "----- stderr -----",
        item.stderr.rstrip(),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _cmd_save_state(args: argparse.Namespace, settings, state_client: PowerContextState) -> int:
    saved = step_save_state(
        state_client,
        args.task_id,
        args.phase,
        done=args.done,
        pending=args.pending,
        verifications=[],
        artifacts=args.artifact,
    )
    saved["scope_id"] = state_client.ensure_scope()
    _emit(args, saved, "状态已写入 PowerContext。\n" + saved["state"]["task_id"])
    return 0


def _cmd_resume(args: argparse.Namespace, state_client: PowerContextState) -> int:
    state = step_resume(state_client, args.task_id)
    payload = state.to_dict() if state else None
    text = state.render() if state else "未找到已保存的任务状态。"
    _emit(args, payload or {}, text)
    return 0 if state else 1


def _cmd_demo(args: argparse.Namespace, settings, state_client: PowerContextState) -> int:
    task_id = args.task_id
    log_dir = Path(args.log_dir) if args.log_dir else settings.project_dir / "logs"
    if args.reset:
        reset_project(settings.project_dir)
    with SeekdbStore(db_dir=settings.db_dir) as store:
        store.create_schema()
        report = step_import(store, settings)
        bundle = step_context(
            store,
            settings,
            task_id,
            args.task,
            None if args.no_state else state_client,
        )
        before_results: list = []
        if not args.skip_verify:
            before_results = step_verify(store, settings, task_id, phase="before")
            for item in before_results:
                _write_suite_log(log_dir, item)
        result = None
        if not args.skip_apply:
            client = _make_client(args)
            result = step_apply(store, settings, bundle, client, apply_patch=True)
        verifications: list = []
        if not args.skip_verify:
            verifications = step_verify(store, settings, task_id, phase="after")
            for item in verifications:
                _write_suite_log(log_dir, item)

        all_results = before_results + verifications
        saved = None
        if not args.no_state:
            saved = step_save_state(
                state_client,
                task_id,
                "after",
                done=[
                    f"导入资料：规格 {report.spec_count} 条 / 代码 {report.code_symbol_count} 个 / 测试 {report.test_case_count} 条",
                    f"MiniMax 完成代码修改：{', '.join(result.applied_files) if result else '（跳过）'}",
                ],
                pending=[] if verifications and all(item.exit_code == 0 for item in verifications) else ["修复未通过的测试"],
                verifications=all_results,
                artifacts=[f"records/minimax_dev_record.md", f"records/db_query_record.md"],
            )

    write_minimax_record(settings, bundle, result)
    with SeekdbStore(db_dir=settings.db_dir) as record_store:
        write_db_record(settings, record_store, bundle, all_results)
    resumed = None
    resolved_scope = None
    if not args.no_state:
        resumed = step_resume(state_client, task_id)
        resolved_scope = state_client.ensure_scope()
        write_state_record(
            settings,
            task_id,
            saved,
            resumed,
            settings.powercontext_url,
            settings.scope_id,
            resolved_scope,
        )

    payload = {
        "task_id": task_id,
        "import": report.to_dict(),
        "specs": [item.spec_id for item in bundle.specs],
        "code": [item.symbol for item in bundle.code],
        "tests": len(bundle.tests),
        "assistant": result.to_dict() if result else None,
        "verifications": [item.to_dict() for item in all_results],
        "state_saved": bool(saved),
        "state_resumed": resumed.to_dict() if resumed else None,
    }
    lines = [
        "演示流程完成。",
        f"- 任务：{bundle.task_text}",
        f"- 规格条目：{', '.join(item.spec_id for item in bundle.specs) or '-'}",
        f"- 代码符号：{', '.join(item.symbol for item in bundle.code) or '-'}",
        f"- 测试用例：{len(bundle.tests)} 条",
        f"- MiniMax：{result.model if result else '（跳过）'}",
    ]
    for item in all_results:
        lines.append(
            f"- 测试 [{item.phase}/{item.suite}] exit={item.exit_code} passed={item.passed} failed={item.failed}"
        )
    lines.append(f"- 状态写入：{'是' if saved else '否'}；重启后读取：{'是' if resumed else '否'}")
    lines.append(f"- 记录目录：{settings.records_dir}")
    _emit(args, payload, "\n".join(lines))
    return 0


def _make_client(args: argparse.Namespace) -> MiniMaxClient:
    """按参数构造 MiniMax 客户端。"""
    transport = getattr(args, "transport", "http")
    recorded = getattr(args, "recorded", None)
    if transport == "file":
        if not recorded:
            raise SystemExit("transport=file 需要 --recorded 指定响应文件")
        return MiniMaxClient(
            transport="file",
            model=getattr(args, "model", None),
            response_file=recorded,
        )
    return MiniMaxClient(transport=transport, model=getattr(args, "model", None))


if __name__ == "__main__":
    sys.exit(main())
