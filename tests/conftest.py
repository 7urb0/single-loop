"""共享夹具：一套订单场景的资产，够跑端到端。"""

from __future__ import annotations

import pytest

from single_loop import Registry, ToolDef


@pytest.fixture
def registry() -> Registry:
    reg = Registry()
    return reg


@pytest.fixture
def order_tools() -> dict[str, ToolDef]:
    """三个工具，串成一条有前置条件的链。

    update_address 需要 get_order 先成功；create_carrier_change 需要 update_address 先成功。
    """

    def get_order(order_id: str) -> dict:
        return {"order_id": order_id, "status": "shipped", "carrier": "中通"}

    def update_address(order_id: str, address: str) -> dict:
        return {"order_id": order_id, "address": address, "ok": True}

    def create_carrier_change(order_id: str, carrier: str) -> dict:
        return {"order_id": order_id, "carrier": carrier, "ticket": "CC-001"}

    return {
        "get_order": ToolDef(
            name="get_order",
            fn=get_order,
            schema={
                "type": "function",
                "function": {
                    "name": "get_order",
                    "description": "按订单号查询订单状态",
                    "parameters": {
                        "type": "object",
                        "properties": {"order_id": {"type": "string"}},
                        "required": ["order_id"],
                    },
                },
            },
            description="按订单号查询订单状态",
        ),
        "update_address": ToolDef(
            name="update_address",
            fn=update_address,
            schema={
                "type": "function",
                "function": {
                    "name": "update_address",
                    "description": "修改收货地址",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"},
                            "address": {"type": "string"},
                        },
                        "required": ["order_id", "address"],
                    },
                },
            },
            description="修改收货地址",
            requires=("get_order",),
        ),
        "create_carrier_change": ToolDef(
            name="create_carrier_change",
            fn=create_carrier_change,
            schema={
                "type": "function",
                "function": {
                    "name": "create_carrier_change",
                    "description": "向承运商提交改派单",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"},
                            "carrier": {"type": "string"},
                        },
                        "required": ["order_id", "carrier"],
                    },
                },
            },
            description="向承运商提交改派单",
            requires=("update_address",),
        ),
    }
