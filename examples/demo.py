"""离线演示：一条订单改地址的链路，走完全部四个机制。

跑法：
    python examples/demo.py
不需要网络，也不需要 API key。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from single_loop import Budget, MainLoop, Registry, ToolDef  # noqa: E402
from single_loop.testing import ScriptedModel, text, tool_call  # noqa: E402


def build_registry() -> tuple[Registry, dict[str, ToolDef]]:
    def get_order(order_id: str) -> dict:
        return {"order_id": order_id, "status": "shipped", "carrier": "中通"}

    def update_address(order_id: str, address: str) -> dict:
        return {"order_id": order_id, "address": address, "ok": True}

    def create_carrier_change(order_id: str, carrier: str) -> dict:
        return {"order_id": order_id, "carrier": carrier, "ticket": "CC-20241120-01"}

    def schema(name: str, desc: str, props: dict, required: list[str]) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }

    tools = {
        "get_order": ToolDef(
            name="get_order",
            fn=get_order,
            schema=schema("get_order", "查订单", {"order_id": {"type": "string"}}, ["order_id"]),
            description="按订单号查询订单状态",
        ),
        "update_address": ToolDef(
            name="update_address",
            fn=update_address,
            schema=schema(
                "update_address",
                "改地址",
                {"order_id": {"type": "string"}, "address": {"type": "string"}},
                ["order_id", "address"],
            ),
            description="修改收货地址",
            requires=("get_order",),
        ),
        "create_carrier_change": ToolDef(
            name="create_carrier_change",
            fn=create_carrier_change,
            schema=schema(
                "create_carrier_change",
                "提改派单",
                {"order_id": {"type": "string"}, "carrier": {"type": "string"}},
                ["order_id", "carrier"],
            ),
            description="向承运商提交改派单",
            requires=("update_address",),
        ),
    }
    return Registry(), tools


SCRIPT = [
    # 第一轮：没检索直接调工具，被挡
    tool_call("update_address", {"order_id": "SO-88231", "address": "杭州西湖区"}),
    # 第二轮：改用检索
    tool_call("discover", {"query": "地址"}),
    # 第三轮：工具加载了，但前置条件没满足
    tool_call("update_address", {"order_id": "SO-88231", "address": "杭州西湖区"}),
    # 第四轮：先查订单
    tool_call("discover", {"query": "订单"}),
    tool_call("get_order", {"order_id": "SO-88231"}, call_id="c-order"),
    # 第五轮：前置条件满足，改地址成功
    tool_call("update_address", {"order_id": "SO-88231", "address": "杭州西湖区"}),
    # 第六轮：提改派单
    tool_call("discover", {"query": "改派"}),
    tool_call("create_carrier_change", {"order_id": "SO-88231", "carrier": "中通"}),
    # 收尾
    text("地址已改到杭州西湖区，改派单 CC-20241120-01 已提交给中通。"),
]


def main() -> int:
    registry, tools = build_registry()
    model = ScriptedModel(SCRIPT)
    loop = MainLoop(model, registry, budget=Budget(max_turns=12, max_repeat_denials=3))
    for tool in tools.values():
        loop.register_tool(tool)

    print("=" * 68)
    print("单循环演示：披露 → 前置条件 → 拒绝反馈 → 完成")
    print("=" * 68)

    result = loop.run("把 SO-88231 的收货地址改到杭州西湖区，客户催得急。")

    for i, seen in enumerate(model.tools_seen, 1):
        print(f"\n第 {i} 轮 模型可见工具：{seen}")

    print("\n" + "-" * 68)
    print("工具调用记录：")
    for message in result.messages:
        if message["role"] == "tool":
            payload = json.loads(message["content"])
            outcome = payload.get("outcome")
            detail = payload.get("detail") or payload.get("note") or ""
            print(f"  {message['tool_call_id']:<12} {outcome:<22} {detail}")

    print("\n" + "-" * 68)
    print(f"轮次：{result.turns}  停止原因：{result.stopped.value}")
    print(f"被拒调用：{result.denied}")
    print(f"形式验收：{result.verification.detail or '通过'}")
    print(f"最终答案：{result.answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
