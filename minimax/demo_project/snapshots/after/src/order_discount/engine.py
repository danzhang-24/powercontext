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
"""满减与会员折扣计算。

规格来源：specs/order_discount.spec.md
"""

from __future__ import annotations

from .models import Order

#: 满减阶梯：(门槛, 减免金额)，门槛单位为元。
DISCOUNT_TIERS: tuple[tuple[float, float], ...] = (
    (600.0, 80.0),
    (300.0, 30.0),
    (100.0, 10.0),
)

#: 会员在满减金额基础上再享受的折扣比例。
MEMBER_DISCOUNT_RATE = 0.05


def compute_discount(order: Order) -> float:
    """计算订单优惠金额。

    Args:
        order: 待计算的订单。

    Returns:
        优惠金额（元），保留两位小数。
    """
    if any(item.fragile for item in order.items):
        return 0.0
    amount = order.subtotal
    discount = 0.0
    for threshold, reduction in DISCOUNT_TIERS:
        if amount >= threshold:
            discount = reduction
            break
    if discount and order.member:
        discount = round(discount * (1 - MEMBER_DISCOUNT_RATE), 2)
    return discount
