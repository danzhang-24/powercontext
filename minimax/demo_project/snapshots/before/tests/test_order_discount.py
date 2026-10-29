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
"""订单优惠计算的功能测试与回归测试。

分组约定：

- ``target``：覆盖规格 SPEC-DISC-002 / SPEC-DISC-003 等"待实现"条目。
  规则实现之前必须失败，规则实现之后必须通过。
- ``regression``：覆盖 SPEC-DISC-001 / SPEC-DISC-004 等"已实现"条目。
  修改前后都必须通过。
"""

import pytest

from order_discount.engine import compute_discount
from order_discount.models import Order, OrderItem


def _order(subtotal, *, shipping=0.0, member=False, fragile=False):
    """构造只含一行的订单，subtotal 即该行小计。"""
    return Order(
        order_id="o-1001",
        items=(OrderItem(sku="sku-1", unit_price=subtotal, quantity=1, fragile=fragile),),
        shipping_fee=shipping,
        member=member,
    )


# --------------------------------------------------------------------------
# 目标功能测试：SPEC-DISC-002 / SPEC-DISC-003
# --------------------------------------------------------------------------


@pytest.mark.target
def test_threshold_ignores_shipping():
    """SPEC-DISC-002：运费不计入满减门槛。"""
    order = _order(95.0, shipping=20.0)
    assert compute_discount(order) == 0.0


@pytest.mark.target
def test_threshold_boundary_excludes_subtotal_below_100():
    """SPEC-DISC-002：门槛取商品小计，小计 99.99 元不满足 100 元门槛。"""
    order = _order(99.99, shipping=0.01)
    assert compute_discount(order) == 0.0


@pytest.mark.target
def test_fragile_order_is_excluded_from_tier_discount():
    """SPEC-DISC-003：含易碎品的订单不享受满减。"""
    order = _order(500.0, fragile=True)
    assert compute_discount(order) == 0.0


@pytest.mark.target
def test_fragile_order_with_shipping_stays_excluded():
    """SPEC-DISC-003：运费不改变易碎品订单不参与满减的结论。"""
    order = _order(95.0, shipping=30.0, fragile=True)
    assert compute_discount(order) == 0.0


# --------------------------------------------------------------------------
# 回归测试：SPEC-DISC-001 / SPEC-DISC-004
# --------------------------------------------------------------------------


@pytest.mark.regression
def test_tier_300_subtotal():
    """SPEC-DISC-001：满 300 元减 30 元。"""
    assert compute_discount(_order(300.0)) == 30.0


@pytest.mark.regression
def test_tier_600_subtotal():
    """SPEC-DISC-001：满 600 元减 80 元，只命中最高一档。"""
    assert compute_discount(_order(600.0)) == 80.0


@pytest.mark.regression
def test_below_threshold_has_no_discount():
    """SPEC-DISC-001：小计 99 元不满足任何门槛。"""
    assert compute_discount(_order(99.0)) == 0.0


@pytest.mark.regression
def test_member_discount_applies_on_tier():
    """SPEC-DISC-004：会员在满减 30 元基础上再打 95 折。"""
    assert compute_discount(_order(300.0, member=True)) == 28.5


@pytest.mark.regression
def test_shipping_does_not_change_qualifying_discount():
    """SPEC-DISC-002：已达门槛的订单，运费不改变优惠金额。"""
    assert compute_discount(_order(120.0, shipping=10.0)) == 10.0


@pytest.mark.regression
def test_empty_order_has_no_discount():
    """SPEC-DISC-004：无商品时没有优惠。"""
    order = Order(order_id="o-1002", items=(), shipping_fee=12.0, member=True)
    assert compute_discount(order) == 0.0
