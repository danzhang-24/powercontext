"""订单与订单行数据模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderItem:
    """订单行。

    Attributes:
        sku: 商品编码。
        unit_price: 单价。
        quantity: 数量。
        fragile: 是否为易碎品。规格 SPEC-DISC-003 的判定依据。
    """

    sku: str
    unit_price: float
    quantity: int
    fragile: bool = False

    @property
    def subtotal(self) -> float:
        return round(self.unit_price * self.quantity, 2)


@dataclass(frozen=True)
class Order:
    """订单。

    Attributes:
        order_id: 订单号。
        items: 订单行。
        shipping_fee: 运费。规格 SPEC-DISC-002 规定运费不计入满减门槛。
        member: 是否会员。规格 SPEC-DISC-004 规定会员在满减金额上再打 95 折。
    """

    order_id: str
    items: tuple[OrderItem, ...]
    shipping_fee: float = 0.0
    member: bool = False

    @property
    def subtotal(self) -> float:
        """商品小计（不含运费）。"""
        return round(sum(item.subtotal for item in self.items), 2)

    @property
    def total(self) -> float:
        """订单实付金额（商品小计 + 运费）。"""
        return round(self.subtotal + self.shipping_fee, 2)
