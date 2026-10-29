"""SQL 字面量与标识符的安全拼接。

seekdb 的 MySQL 协议驱动支持参数绑定，但向量列、全文检索表达式等场景需要把
字面量直接写进 SQL（例如 ``l2_distance(emb, '[0.1,0.2]')``、``AI_EMBED('m', '...')``），
因此这里统一提供转义函数，避免各处手写引号导致注入或语法错误。
"""

from __future__ import annotations

from typing import Iterable, Sequence


def quote_ident(name: str) -> str:
    """把标识符包成反引号形式，内部反引号按 SQL 规则转义。"""
    return "`" + name.replace("`", "``") + "`"


def sql_str(value: str) -> str:
    """把字符串转义成 SQL 单引号字面量（含转义与反斜杠处理）。"""
    escaped = (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\x00", "\\0")
    )
    return f"'{escaped}'"


def sql_int(value: int) -> str:
    """把整数转成 SQL 字面量。"""
    return str(int(value))


def sql_float(value: float) -> str:
    """把浮点数转成 SQL 字面量，保留 6 位小数并避免科学计数法。"""
    return f"{float(value):.6f}"


def sql_vector(values: Sequence[float]) -> str:
    """把向量转成 seekdb ``vector(N)`` 列可接受的字符串字面量。"""
    body = ",".join(f"{float(value):.6f}" for value in values)
    return sql_str(f"[{body}]")


def sql_like(value: str) -> str:
    """转义 ``LIKE`` 模式中的通配符。"""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def sql_in_list(values: Iterable[str]) -> str:
    """把字符串列表转成 ``'a', 'b'`` 形式的列表。"""
    items = list(values)
    if not items:
        return "NULL"
    return ", ".join(sql_str(item) for item in items)
