"""SDD 上下文模块（sddctx）。

模块职责：根据开发任务检索规格、代码与测试，形成可交给 MiniMax 的开发上下文，
并在任务推进过程中用 PowerContext 保存 / 恢复任务状态。

子命令入口见 ``python -m sddctx --help``。
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
